#!/usr/bin/env python3
"""
SWE-bench Post-Benchmark Analysis & Cleanup Runner.

Comprehensive post-evaluation tooling to:
1. Parse and consolidate SWE-bench harness evaluation results and agent generation reports.
2. Calculate overall and per-repository resolution rates, pass rates, and token economics.
3. Automatically locate and extract high-signal failure logs, test error tracebacks, and regression details.
4. Export unresolved/failed task instances to plain text or filtered JSONL files for targeted re-runs.
5. Provide automated Docker container/image cleanup and repo disk cache management.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Terminal styling helpers
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def supports_color() -> bool:
    """Check if stdout supports ANSI color formatting."""
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


def c(text: str, color_code: str) -> str:
    """Apply ANSI color if supported."""
    return f"{color_code}{text}{Colors.RESET}" if supports_color() else text


@dataclass
class FailureDetails:
    instance_id: str
    failure_category: str  # e.g., "FAIL_TO_PASS_FAILED", "PASS_TO_PASS_REGRESSION", "PATCH_APPLY_FAILED", "EMPTY_PATCH", "EXECUTION_ERROR"
    failed_tests: List[str] = field(default_factory=list)
    passed_tests: List[str] = field(default_factory=list)
    patch_applied: Optional[bool] = None
    log_snippet: str = ""
    log_file_path: Optional[str] = None
    report_file_path: Optional[str] = None


@dataclass
class EvaluationSummary:
    run_id: str
    total_submitted: int = 0
    total_completed: int = 0
    total_resolved: int = 0
    total_unresolved: int = 0
    total_error: int = 0
    total_empty_patch: int = 0
    resolution_rate_percent: float = 0.0
    resolved_ids: List[str] = field(default_factory=list)
    unresolved_ids: List[str] = field(default_factory=list)
    error_ids: List[str] = field(default_factory=list)
    empty_patch_ids: List[str] = field(default_factory=list)
    submitted_ids: List[str] = field(default_factory=list)
    repo_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failures: Dict[str, FailureDetails] = field(default_factory=dict)
    agent_report: Optional[Dict[str, Any]] = None
    source_files: List[str] = field(default_factory=list)


def extract_repo_from_instance_id(instance_id: str) -> str:
    """Extract repository identifier from SWE-bench instance ID (e.g. 'astropy__astropy-12907' -> 'astropy/astropy')."""
    if "__" in instance_id:
        repo_prefix = instance_id.split("__")[0]
        # Common SWE-bench repo naming convention: org__repo-issue -> org/repo
        parts = instance_id.split("__")
        org = parts[0]
        repo_and_num = parts[1]
        repo_name = repo_and_num.rsplit("-", 1)[0]
        return f"{org}/{repo_name}"
    return "unknown"


def find_eval_report_files(explicit_paths: Optional[List[str]] = None, run_id: Optional[str] = None) -> List[Path]:
    """Locate harness evaluation JSON files matching patterns or explicit inputs."""
    found: List[Path] = []
    
    if explicit_paths:
        for p in explicit_paths:
            path_obj = Path(p)
            if path_obj.is_file():
                found.append(path_obj.resolve())
            elif path_obj.is_dir():
                found.extend(sorted(path_obj.glob("*.json")))
            else:
                # Check glob
                for matched in glob.glob(p):
                    found.append(Path(matched).resolve())

    if not found:
        search_patterns = [
            "evaluation_results/*.json",
            "*.eval.json",
            "*eval*.json",
        ]
        if run_id:
            search_patterns.insert(0, f"evaluation_results/*{run_id}*.json")
            search_patterns.insert(1, f"*{run_id}*.json")

        for pattern in search_patterns:
            for matched in glob.glob(pattern):
                p = Path(matched).resolve()
                if p.name != "evaluation_report.json" and p not in found:
                    found.append(p)

    return found


def find_agent_report_file(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Locate the agent generation report JSON file (e.g. evaluation_report.json)."""
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.is_file():
            return p

    default_candidates = [
        Path("evaluation_report.json"),
        Path("reports/evaluation_report.json"),
    ]
    for cand in default_candidates:
        if cand.is_file():
            return cand.resolve()

    return None


def locate_instance_logs(instance_id: str, run_id: Optional[str] = None) -> Dict[str, Optional[Path]]:
    """Search workspace logs/run_evaluation/ for report.json, run_instance.log, and test_output.txt."""
    results: Dict[str, Optional[Path]] = {
        "report_json": None,
        "run_log": None,
        "test_output": None,
        "eval_sh": None,
        "patch_diff": None,
    }

    base_dir = Path("logs/run_evaluation")
    if not base_dir.exists():
        return results

    # Candidate search directories
    candidates = []
    if run_id:
        candidates.extend(base_dir.glob(f"{run_id}/**/{instance_id}"))
        candidates.extend(base_dir.glob(f"*{run_id}*/**/{instance_id}"))
    
    candidates.extend(base_dir.glob(f"**/{instance_id}"))

    for candidate_dir in candidates:
        if candidate_dir.is_dir():
            rep = candidate_dir / "report.json"
            run_l = candidate_dir / "run_instance.log"
            test_o = candidate_dir / "test_output.txt"
            eval_s = candidate_dir / "eval.sh"
            patch_d = candidate_dir / "patch.diff"

            if rep.exists() and not results["report_json"]:
                results["report_json"] = rep
            if run_l.exists() and not results["run_log"]:
                results["run_log"] = run_l
            if test_o.exists() and not results["test_output"]:
                results["test_output"] = test_o
            if eval_s.exists() and not results["eval_sh"]:
                results["eval_sh"] = eval_s
            if patch_d.exists() and not results["patch_diff"]:
                results["patch_diff"] = patch_d

            if results["report_json"] and (results["run_log"] or results["test_output"]):
                break

    return results


def extract_high_signal_failure_snippet(log_path: Optional[Path], max_lines: int = 25) -> str:
    """Extract the most diagnostic lines from a test run log (tracebacks, assertion errors, pytest failures)."""
    if not log_path or not log_path.exists():
        return "No log file available."

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading log file: {e}"

    lines = content.splitlines()
    if not lines:
        return "Log file is empty."

    # Look for key failure signatures
    failure_patterns = [
        r"=+\s+FAILURES\s+=+",
        r"=+\s+ERRORS\s+=+",
        r"=+\s+short test summary info\s+=+",
        r"Traceback \(most recent call last\):",
        r"FAILED\s+[^\s]+",
        r"AssertionError",
        r"error: patch failed:",
        r"patch does not apply",
    ]

    best_start = -1
    for pattern in failure_patterns:
        for idx, line in enumerate(lines):
            if re.search(pattern, line):
                best_start = idx
                break
        if best_start != -1:
            break

    if best_start != -1:
        # Grab lines starting from failure marker
        selected = lines[best_start : best_start + max_lines]
        return "\n".join(selected).strip()

    # If no standard failure pattern was matched, return the last max_lines
    tail = lines[-max_lines:]
    return "\n".join(tail).strip()


def inspect_failure_for_instance(instance_id: str, run_id: Optional[str] = None) -> FailureDetails:
    """Perform deep diagnostics on a failing instance by parsing instance report.json and test logs."""
    log_files = locate_instance_logs(instance_id, run_id)
    
    failure = FailureDetails(
        instance_id=instance_id,
        failure_category="UNRESOLVED",
        log_file_path=str(log_files["run_log"]) if log_files["run_log"] else None,
        report_file_path=str(log_files["report_json"]) if log_files["report_json"] else None,
    )

    # 1. Parse instance report.json if present
    if log_files["report_json"]:
        try:
            with open(log_files["report_json"], "r", encoding="utf-8") as f:
                data = json.load(f)
                
            inst_data = data.get(instance_id, data)
            if isinstance(inst_data, dict):
                patch_applied = inst_data.get("patch_successfully_applied")
                patch_exists = inst_data.get("patch_exists")
                failure.patch_applied = patch_applied

                if patch_exists is False or inst_data.get("patch_is_None"):
                    failure.failure_category = "EMPTY_PATCH"
                elif patch_applied is False:
                    failure.failure_category = "PATCH_APPLY_FAILED"

                tests_status = inst_data.get("tests_status", {})
                f2p = tests_status.get("FAIL_TO_PASS", {})
                p2p = tests_status.get("PASS_TO_PASS", {})

                f2p_fail = f2p.get("failure", [])
                p2p_fail = p2p.get("failure", [])
                f2p_succ = f2p.get("success", [])
                p2p_succ = p2p.get("success", [])

                failure.failed_tests = [f"[F2P] {t}" for t in f2p_fail] + [f"[P2P Regression] {t}" for t in p2p_fail]
                failure.passed_tests = [f"[F2P] {t}" for t in f2p_succ] + [f"[P2P] {t}" for t in p2p_succ]

                if p2p_fail and not f2p_fail:
                    failure.failure_category = "PASS_TO_PASS_REGRESSION"
                elif f2p_fail:
                    failure.failure_category = "FAIL_TO_PASS_FAILED"
        except Exception:
            pass

    # 2. Extract diagnostic log snippet
    target_log = log_files["test_output"] or log_files["run_log"]
    failure.log_snippet = extract_high_signal_failure_snippet(target_log)

    return failure


def parse_evaluation_results(
    report_paths: List[Path],
    run_id: Optional[str] = None,
    extract_logs: bool = True,
) -> EvaluationSummary:
    """Parse one or multiple evaluation result JSON files and build consolidated summary."""
    resolved_set: Set[str] = set()
    unresolved_set: Set[str] = set()
    error_set: Set[str] = set()
    empty_patch_set: Set[str] = set()
    submitted_set: Set[str] = set()
    completed_set: Set[str] = set()
    source_files: List[str] = []
    
    detected_run_id = run_id or ""

    for path in report_paths:
        if not path.exists():
            continue
        source_files.append(str(path))
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(c(f"⚠️ Warning: Could not parse {path}: {e}", Colors.YELLOW), file=sys.stderr)
            continue

        if not detected_run_id and "run_id" in data:
            detected_run_id = str(data["run_id"])
        elif not detected_run_id:
            # Try to infer run_id from filename (e.g. minovative-mind-agent.pilot_eval.json)
            parts = path.stem.split(".")
            if len(parts) >= 2:
                detected_run_id = parts[-1]

        # Extract IDs
        for inst_id in data.get("resolved_ids", []):
            resolved_set.add(inst_id)
        for inst_id in data.get("unresolved_ids", []):
            unresolved_set.add(inst_id)
        for inst_id in data.get("error_ids", []):
            error_set.add(inst_id)
        for inst_id in data.get("empty_patch_ids", []):
            empty_patch_set.add(inst_id)
        for inst_id in data.get("submitted_ids", []):
            submitted_set.add(inst_id)
        for inst_id in data.get("completed_ids", []):
            completed_set.add(inst_id)

    # If submitted_set is empty, union of all sets
    if not submitted_set:
        submitted_set = resolved_set.union(unresolved_set).union(error_set).union(empty_patch_set)

    total_submitted = len(submitted_set)
    total_resolved = len(resolved_set)
    total_unresolved = len(unresolved_set)
    total_error = len(error_set)
    total_empty_patch = len(empty_patch_set)
    total_completed = len(completed_set) or (total_resolved + total_unresolved)

    pass_rate = (total_resolved / max(total_submitted, 1)) * 100.0

    # Build per-repository breakdown
    repo_breakdown: Dict[str, Dict[str, Any]] = {}
    for inst_id in sorted(submitted_set):
        repo = extract_repo_from_instance_id(inst_id)
        if repo not in repo_breakdown:
            repo_breakdown[repo] = {
                "submitted": 0,
                "resolved": 0,
                "unresolved": 0,
                "error": 0,
                "pass_rate_percent": 0.0,
                "instances": [],
            }
        repo_breakdown[repo]["submitted"] += 1
        
        status = "unresolved"
        if inst_id in resolved_set:
            repo_breakdown[repo]["resolved"] += 1
            status = "resolved"
        elif inst_id in error_set:
            repo_breakdown[repo]["error"] += 1
            status = "error"
        else:
            repo_breakdown[repo]["unresolved"] += 1

        repo_breakdown[repo]["instances"].append({"instance_id": inst_id, "status": status})

    for repo, stats in repo_breakdown.items():
        stats["pass_rate_percent"] = round(
            (stats["resolved"] / max(stats["submitted"], 1)) * 100.0, 1
        )

    # Perform failure inspection on failed instances
    failures_dict: Dict[str, FailureDetails] = {}
    failed_instances = sorted(unresolved_set.union(error_set).union(empty_patch_set))
    
    if extract_logs:
        for inst_id in failed_instances:
            failures_dict[inst_id] = inspect_failure_for_instance(inst_id, detected_run_id)

    summary = EvaluationSummary(
        run_id=detected_run_id or "swebench_eval",
        total_submitted=total_submitted,
        total_completed=total_completed,
        total_resolved=total_resolved,
        total_unresolved=total_unresolved,
        total_error=total_error,
        total_empty_patch=total_empty_patch,
        resolution_rate_percent=round(pass_rate, 2),
        resolved_ids=sorted(list(resolved_set)),
        unresolved_ids=sorted(list(unresolved_set)),
        error_ids=sorted(list(error_set)),
        empty_patch_ids=sorted(list(empty_patch_set)),
        submitted_ids=sorted(list(submitted_set)),
        repo_breakdown=repo_breakdown,
        failures=failures_dict,
        source_files=source_files,
    )

    return summary


def display_scorecard(summary: EvaluationSummary, agent_report: Optional[Dict[str, Any]] = None) -> None:
    """Render a terminal evaluation scorecard."""
    width = 75
    print("\n" + c("=" * width, Colors.BOLD))
    print(c("  🏆 SWE-BENCH POST-BENCHMARK EVALUATION SCORECARD", Colors.BOLD + Colors.CYAN))
    print(c("=" * width, Colors.BOLD))

    print(f"  {c('Run Identifier:', Colors.BOLD):<30} {summary.run_id}")
    if summary.source_files:
        print(f"  {c('Report Source(s):', Colors.BOLD):<30} {', '.join([Path(f).name for f in summary.source_files])}")
    print(f"  {c('Total Tasks Evaluated:', Colors.BOLD):<30} {summary.total_submitted}")
    print(f"  {c('Successfully Resolved:', Colors.BOLD):<30} {c(str(summary.total_resolved), Colors.GREEN)} ({summary.resolution_rate_percent:.1f}%)")
    
    unres_color = Colors.RED if summary.total_unresolved > 0 else Colors.RESET
    print(f"  {c('Unresolved Instances:', Colors.BOLD):<30} {c(str(summary.total_unresolved), unres_color)}")
    
    if summary.total_error > 0:
        print(f"  {c('Harness Execution Errors:', Colors.BOLD):<30} {c(str(summary.total_error), Colors.RED)}")
    if summary.total_empty_patch > 0:
        print(f"  {c('Empty Patches Generated:', Colors.BOLD):<30} {c(str(summary.total_empty_patch), Colors.YELLOW)}")

    print(c("-" * width, Colors.DIM))

    # Per-repository breakdown table
    print(c("  📊 REPOSITORY RESOLUTION BREAKDOWN", Colors.BOLD + Colors.BLUE))
    print(f"  {'Repository':<30} {'Resolved':<10} {'Total':<10} {'Resolution Rate'}")
    print("  " + "-" * 65)
    for repo, stats in sorted(summary.repo_breakdown.items()):
        res = stats["resolved"]
        tot = stats["submitted"]
        rate = stats["pass_rate_percent"]
        rate_str = f"{rate:>6.1f}%"
        if rate == 100.0:
            rate_styled = c(rate_str, Colors.GREEN)
        elif rate > 0.0:
            rate_styled = c(rate_str, Colors.YELLOW)
        else:
            rate_styled = c(rate_str, Colors.RED)

        print(f"  {repo:<30} {res:<10} {tot:<10} {rate_styled}")

    # Agent Generation Metrics & Economics (if available)
    if agent_report:
        print(c("-" * width, Colors.DIM))
        print(c("  🤖 AGENT GENERATION & TOKEN ECONOMICS", Colors.BOLD + Colors.BLUE))
        agent_sum = agent_report.get("summary", {})
        tokens = agent_report.get("token_economics", {})
        recovery = agent_report.get("recovery_metrics", {})

        succeeded = agent_sum.get("succeeded", "N/A")
        total_gen = agent_sum.get("total_instances", "N/A")
        gen_rate = agent_sum.get("success_rate_percent", "N/A")
        avg_dur = agent_sum.get("average_duration_seconds", "N/A")
        avg_patch = agent_sum.get("average_patch_characters", "N/A")

        print(f"  {c('Generation Patch Rate:', Colors.BOLD):<30} {succeeded}/{total_gen} ({gen_rate}%)")
        if avg_dur != "N/A":
            print(f"  {c('Average Agent Latency:', Colors.BOLD):<30} {avg_dur:.1f}s / instance")
        if avg_patch != "N/A":
            print(f"  {c('Average Patch Size:', Colors.BOLD):<30} {avg_patch:.0f} chars")

        if tokens:
            total_tok = tokens.get("total_tokens", 0)
            cached_tok = tokens.get("total_cached_tokens", 0)
            cache_hit = tokens.get("cache_hit_rate_percent", 0)
            print(f"  {c('Total Tokens Consumed:', Colors.BOLD):<30} {total_tok:,}")
            print(f"  {c('Prompt Cache Hit Rate:', Colors.BOLD):<30} {c(f'{cache_hit:.1f}%', Colors.GREEN)} ({cached_tok:,} cached tokens)")

        if recovery:
            cb_trips = recovery.get("circuit_breaker_trips", 0)
            pruned_lines = recovery.get("pruned_log_lines", 0)
            if cb_trips or pruned_lines:
                print(f"  {c('Circuit Breaker Trips:', Colors.BOLD):<30} {cb_trips} trips, {pruned_lines:,} lines pruned")

    print(c("=" * width, Colors.BOLD) + "\n")


def display_failure_diagnostics(summary: EvaluationSummary, max_display: int = 5) -> None:
    """Print failure diagnostics and log snippets for unresolved tasks."""
    if not summary.failures:
        if summary.total_unresolved == 0 and summary.total_error == 0:
            print(c("🎉 All evaluated tasks resolved successfully! No failures to report.\n", Colors.GREEN + Colors.BOLD))
        return

    print(c("=" * 75, Colors.BOLD))
    print(c(f"  🔍 FAILURE DIAGNOSTICS & TEST LOG EXCERPTS ({len(summary.failures)} Failing Tasks)", Colors.BOLD + Colors.RED))
    print(c("=" * 75, Colors.BOLD))

    displayed = 0
    for inst_id, details in summary.failures.items():
        if displayed >= max_display:
            remaining = len(summary.failures) - displayed
            print(c(f"  ... and {remaining} more failing instance(s). Use --export-failures or --all-logs to view all.\n", Colors.DIM))
            break

        displayed += 1
        print(f"\n  {c('Instance:', Colors.BOLD)} {c(inst_id, Colors.CYAN)}")
        print(f"  {c('Failure Category:', Colors.BOLD)} {c(details.failure_category, Colors.YELLOW)}")
        
        if details.failed_tests:
            print(f"  {c('Failed Tests:', Colors.BOLD)} {', '.join(details.failed_tests[:5])}")
            if len(details.failed_tests) > 5:
                print(f"               ... +{len(details.failed_tests) - 5} more failed tests")

        if details.log_file_path:
            print(f"  {c('Log File:', Colors.BOLD)} {details.log_file_path}")

        print(c("  Diagnostic Log Snippet:", Colors.BOLD))
        print("  " + "-" * 70)
        snippet_lines = details.log_snippet.splitlines()
        for s_line in snippet_lines[:15]:
            print(f"    {s_line}")
        if len(snippet_lines) > 15:
            print(f"    ... [{len(snippet_lines) - 15} lines truncated]")
        print("  " + "-" * 70)

    print("")


def export_unresolved_instances(
    summary: EvaluationSummary,
    txt_path: Optional[str] = None,
    jsonl_path: Optional[str] = None,
    instances_source_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Export unresolved instance IDs to text or filtered JSONL file."""
    unresolved = sorted(summary.unresolved_ids + summary.error_ids + summary.empty_patch_ids)
    
    written_txt = None
    written_jsonl = None

    if txt_path:
        out_txt = Path(txt_path).resolve()
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        with open(out_txt, "w", encoding="utf-8") as f:
            for inst in unresolved:
                f.write(f"{inst}\n")
        written_txt = str(out_txt)
        print(f"  ✓ Exported {len(unresolved)} unresolved instance IDs to: {written_txt}")

    if jsonl_path:
        out_jsonl = Path(jsonl_path).resolve()
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        
        source_instances_file = Path(instances_source_path or "test_instances.jsonl")
        if not source_instances_file.exists():
            print(c(f"  ⚠️ Warning: Source instances file '{source_instances_file}' not found; cannot filter JSONL.", Colors.YELLOW), file=sys.stderr)
        else:
            unresolved_set = set(unresolved)
            matched_count = 0
            with open(source_instances_file, "r", encoding="utf-8") as src_f, open(out_jsonl, "w", encoding="utf-8") as dst_f:
                for line in src_f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                        if data.get("instance_id") in unresolved_set:
                            dst_f.write(line_str + "\n")
                            matched_count += 1
                    except json.JSONDecodeError:
                        continue
            written_jsonl = str(out_jsonl)
            print(f"  ✓ Exported {matched_count} filtered unresolved instances to JSONL: {written_jsonl}")

    return written_txt, written_jsonl


def print_targeted_rerun_command(summary: EvaluationSummary, txt_path: Optional[str] = None, jsonl_path: Optional[str] = None) -> None:
    """Display ready-to-run shell commands to re-run unresolved tasks."""
    unresolved = sorted(summary.unresolved_ids + summary.error_ids + summary.empty_patch_ids)
    if not unresolved:
        return

    print(c("=" * 75, Colors.BOLD))
    print(c("  🔁 TARGETED RE-RUN INSTRUCTIONS", Colors.BOLD + Colors.CYAN))
    print(c("=" * 75, Colors.BOLD))

    if len(unresolved) <= 4:
        instances_arg = " ".join([f"--instance-id {inst}" for inst in unresolved])
        print("  Run directly with run_pipeline.sh:")
        print(f"    {c(f'./run_pipeline.sh {instances_arg}', Colors.GREEN)}\n")
    
    if jsonl_path:
        print("  Run filtered JSONL batch with run_pipeline.sh:")
        print(f"    {c(f'./run_pipeline.sh --instances {jsonl_path}', Colors.GREEN)}\n")
    elif txt_path:
        print("  Re-run using exported instance IDs:")
        print(f"    {c(f'./run_pipeline.sh --instance-id $(cat {txt_path} | tr \"\\n\" \" \")', Colors.GREEN)}\n")
    else:
        print("  Re-run only unresolved tasks:")
        print(f"    {c(f'./post_eval.sh --export-unresolved unresolved_instances.txt', Colors.YELLOW)}")
        print(f"    {c('./run_pipeline.sh --instance-id ' + ' '.join(unresolved[:3]) + ' ...', Colors.GREEN)}\n")

    print(c("=" * 75, Colors.BOLD) + "\n")


# ==============================================================================
# Docker & Cache Cleanup Utilities
# ==============================================================================

def get_docker_disk_usage() -> Dict[str, Any]:
    """Retrieve Docker containers and SWE-bench image stats."""
    usage: Dict[str, Any] = {
        "docker_available": False,
        "swebench_images": [],
        "stopped_eval_containers": [],
    }

    docker_bin = shutil.which("docker")
    if not docker_bin:
        return usage

    try:
        # Check running daemon
        info_res = subprocess.run([docker_bin, "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if info_res.returncode != 0:
            return usage
        usage["docker_available"] = True

        # Find SWE-bench images
        img_res = subprocess.run(
            [docker_bin, "images", "--format", "{{.Repository}}:{{.Tag}} ({{.Size}})", "--filter", "reference=swebench/*"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
        )
        if img_res.returncode == 0:
            usage["swebench_images"].extend([line.strip() for line in img_res.stdout.splitlines() if line.strip()])

        # Also search for local sweb.eval images
        img_local_res = subprocess.run(
            [docker_bin, "images", "--format", "{{.Repository}}:{{.Tag}} ({{.Size}})", "--filter", "reference=sweb.eval*"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
        )
        if img_local_res.returncode == 0:
            usage["swebench_images"].extend([line.strip() for line in img_local_res.stdout.splitlines() if line.strip()])

        # Find stopped eval containers
        ps_res = subprocess.run(
            [docker_bin, "ps", "-a", "--filter", "status=exited", "--format", "{{.ID}} {{.Names}}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
        )
        if ps_res.returncode == 0:
            for line in ps_res.stdout.splitlines():
                if "swe" in line.lower() or "eval" in line.lower():
                    usage["stopped_eval_containers"].append(line.strip())

    except Exception:
        pass

    return usage


def get_cache_disk_usage(cache_path: Optional[str] = None) -> Tuple[int, str]:
    """Calculate directory size of SWE-bench repository cache."""
    target_cache = Path(cache_path or os.path.expanduser("~/.cache/swe-bench-repos"))
    if not target_cache.exists():
        return 0, "0 B"

    total_bytes = 0
    try:
        for root, _, files in os.walk(target_cache):
            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):
                    total_bytes += os.path.getsize(fp)
    except Exception:
        pass

    # Format human-readable size
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if total_bytes < 1024.0:
            return total_bytes, f"{total_bytes:.1f} {unit}"
        total_bytes /= 1024.0

    return int(total_bytes * 1024.0), f"{total_bytes:.1f} PB"


def clean_docker_resources(
    clean_containers: bool = False,
    clean_images: bool = False,
    clean_all: bool = False,
    dry_run: bool = False,
) -> None:
    """Remove evaluation containers and images."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("  ⚠️ Docker is not installed or accessible; skipping Docker cleanup.", file=sys.stderr)
        return

    print(c("\n🐳 Docker Resource Cleanup:", Colors.BOLD + Colors.CYAN))

    if clean_containers or clean_all:
        print("  🧹 Removing stopped evaluation containers...")
        if dry_run:
            print("     [DRY-RUN] Would run: docker container prune -f")
        else:
            try:
                res = subprocess.run([docker_bin, "container", "prune", "-f"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    print("     ✓ Stopped containers pruned.")
                else:
                    print(f"     ⚠️ Container prune warning: {res.stderr.strip()}")
            except Exception as e:
                print(f"     ❌ Container prune failed: {e}")

    if clean_images or clean_all:
        print("  🧹 Removing SWE-bench evaluation images...")
        if dry_run:
            print("     [DRY-RUN] Would remove SWE-bench container images and run: docker image prune -f")
        else:
            try:
                # Find image IDs for swebench
                imgs = subprocess.run(
                    [docker_bin, "images", "-q", "--filter", "reference=swebench/*"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if imgs.returncode == 0 and imgs.stdout.strip():
                    img_ids = imgs.stdout.strip().split()
                    subprocess.run([docker_bin, "rmi", "-f"] + img_ids, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Prune dangling
                subprocess.run([docker_bin, "image", "prune", "-f"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("     ✓ SWE-bench images and dangling build layers removed.")
            except Exception as e:
                print(f"     ❌ Image removal failed: {e}")

    if clean_all:
        print("  🧹 Performing complete Docker system cache cleanup...")
        if dry_run:
            print("     [DRY-RUN] Would run: docker builder prune -f")
        else:
            try:
                subprocess.run([docker_bin, "builder", "prune", "-f"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("     ✓ Docker builder cache pruned.")
            except Exception:
                pass


def clean_repository_cache(cache_path: Optional[str] = None, dry_run: bool = False) -> None:
    """Clear local git repository clone cache."""
    target_cache = Path(cache_path or os.path.expanduser("~/.cache/swe-bench-repos"))
    print(c("\n💾 Disk Cache Cleanup:", Colors.BOLD + Colors.CYAN))
    
    if not target_cache.exists():
        print(f"  ℹ️ Cache directory '{target_cache}' does not exist (already clean).")
        return

    _, size_str = get_cache_disk_usage(str(target_cache))
    print(f"  Target: {target_cache} ({size_str})")

    if dry_run:
        print(f"  [DRY-RUN] Would delete: {target_cache}")
        return

    try:
        shutil.rmtree(target_cache)
        print(f"  ✓ Cleared cache directory: {target_cache}")
    except Exception as e:
        print(f"  ❌ Failed to clear cache directory: {e}", file=sys.stderr)


# ==============================================================================
# CLI Argument Parser & Main
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SWE-bench Post-Benchmark Analysis, Failure Extraction, and Cleanup Utility",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input reports & run identification
    parser.add_argument(
        "-r", "--report",
        type=str,
        nargs="*",
        default=[],
        help="Path(s) or glob pattern to SWE-bench harness evaluation JSON report(s) (e.g. *.eval.json)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="",
        help="Evaluation Run ID to locate logs and evaluation results",
    )
    parser.add_argument(
        "--agent-report",
        type=str,
        default=None,
        help="Path to agent prediction generation report JSON (e.g. evaluation_report.json)",
    )

    # Output & Export options
    parser.add_argument(
        "-o", "--output-summary",
        type=str,
        default=None,
        help="Save consolidated post-eval scorecard to JSON file",
    )
    parser.add_argument(
        "-u", "--export-unresolved",
        type=str,
        default=None,
        help="Export unresolved/failing instance IDs to a text file (one ID per line)",
    )
    parser.add_argument(
        "--export-unresolved-jsonl",
        type=str,
        default=None,
        help="Export unresolved instances as a filtered JSONL dataset for re-running",
    )
    parser.add_argument(
        "--instances-source",
        type=str,
        default="test_instances.jsonl",
        help="Source instances JSONL file to filter for --export-unresolved-jsonl",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full scorecard as structured JSON to stdout",
    )

    # Log inspection options
    parser.add_argument(
        "--max-failures",
        type=int,
        default=5,
        help="Maximum number of failure logs to display in terminal",
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Skip searching and extracting test failure log snippets",
    )

    # Cleanup options
    parser.add_argument(
        "--clean-docker-containers",
        action="store_true",
        help="Remove stopped SWE-bench evaluation containers",
    )
    parser.add_argument(
        "--clean-docker-images",
        action="store_true",
        help="Remove local SWE-bench Docker container images",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Clear SWE-bench repository disk cache (~/.cache/swe-bench-repos)",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Custom repository cache directory path",
    )
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="Perform all cleanup tasks (containers, images, builder cache, and repo cache)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate cleanup operations without deleting anything",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 1. Locate Evaluation Report Files
    eval_report_paths = find_eval_report_files(args.report, args.run_id)
    agent_report_path = find_agent_report_file(args.agent_report)

    agent_report_data: Optional[Dict[str, Any]] = None
    if agent_report_path and agent_report_path.exists():
        try:
            with open(agent_report_path, "r", encoding="utf-8") as f:
                agent_report_data = json.load(f)
        except Exception as e:
            print(c(f"⚠️ Warning: Failed to read agent report {agent_report_path}: {e}", Colors.YELLOW), file=sys.stderr)

    # 2. Parse Evaluation Reports
    if not eval_report_paths:
        # If no harness results found, but agent report exists, construct partial summary
        if agent_report_data:
            summary = EvaluationSummary(
                run_id=args.run_id or "agent_run",
                agent_report=agent_report_data,
                source_files=[str(agent_report_path)] if agent_report_path else [],
            )
            agent_sum = agent_report_data.get("summary", {})
            summary.total_submitted = agent_sum.get("total_instances", 0)
            summary.total_resolved = agent_sum.get("succeeded", 0)
            summary.total_unresolved = agent_sum.get("failed", 0)
            summary.resolution_rate_percent = float(agent_sum.get("success_rate_percent", 0.0))
            
            for inst in agent_report_data.get("instances", []):
                inst_id = inst.get("instance_id")
                if not inst_id:
                    continue
                summary.submitted_ids.append(inst_id)
                if inst.get("success"):
                    summary.resolved_ids.append(inst_id)
                else:
                    summary.unresolved_ids.append(inst_id)
        else:
            print(c("❌ Error: No evaluation report files found (checked evaluation_results/*.json, *.eval.json, evaluation_report.json).", Colors.RED), file=sys.stderr)
            print("   Please provide a report path via -r / --report or specify --run-id.", file=sys.stderr)
            
            # Still perform cleanup if requested
            if args.clean_docker_containers or args.clean_docker_images or args.clean_cache or args.clean_all:
                if args.clean_docker_containers or args.clean_docker_images or args.clean_all:
                    clean_docker_resources(args.clean_docker_containers, args.clean_docker_images, args.clean_all, args.dry_run)
                if args.clean_cache or args.clean_all:
                    clean_repository_cache(args.cache_dir, args.dry_run)
                return 0
            return 1
    else:
        summary = parse_evaluation_results(
            eval_report_paths,
            run_id=args.run_id,
            extract_logs=not args.no_logs,
        )
        summary.agent_report = agent_report_data

    # 3. Output formats
    if args.json:
        export_dict = {
            "run_id": summary.run_id,
            "total_submitted": summary.total_submitted,
            "total_completed": summary.total_completed,
            "total_resolved": summary.total_resolved,
            "total_unresolved": summary.total_unresolved,
            "total_error": summary.total_error,
            "total_empty_patch": summary.total_empty_patch,
            "resolution_rate_percent": summary.resolution_rate_percent,
            "resolved_ids": summary.resolved_ids,
            "unresolved_ids": summary.unresolved_ids,
            "error_ids": summary.error_ids,
            "repo_breakdown": summary.repo_breakdown,
            "failures": {
                k: {
                    "instance_id": v.instance_id,
                    "category": v.failure_category,
                    "failed_tests": v.failed_tests,
                    "log_file": v.log_file_path,
                }
                for k, v in summary.failures.items()
            },
        }
        print(json.dumps(export_dict, indent=2))
    else:
        display_scorecard(summary, agent_report_data)
        if not args.no_logs:
            display_failure_diagnostics(summary, max_display=args.max_failures)

    # 4. Export Unresolved Instances for Re-runs
    txt_export = args.export_unresolved
    jsonl_export = args.export_unresolved_jsonl
    if txt_export or jsonl_export:
        print(c("📁 Exporting Unresolved Tasks for Targeted Iteration:", Colors.BOLD + Colors.BLUE))
        export_unresolved_instances(
            summary,
            txt_path=txt_export,
            jsonl_path=jsonl_export,
            instances_source_path=args.instances_source,
        )
        print("")

    if not args.json and (summary.unresolved_ids or summary.error_ids):
        print_targeted_rerun_command(summary, txt_path=txt_export, jsonl_path=jsonl_export)

    # 5. Output Summary File
    if args.output_summary:
        out_path = Path(args.output_summary).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary_payload = {
            "run_id": summary.run_id,
            "timestamp": str(os.path.getmtime(eval_report_paths[0])) if eval_report_paths else None,
            "total_submitted": summary.total_submitted,
            "total_resolved": summary.total_resolved,
            "total_unresolved": summary.total_unresolved,
            "total_error": summary.total_error,
            "resolution_rate_percent": summary.resolution_rate_percent,
            "resolved_ids": summary.resolved_ids,
            "unresolved_ids": summary.unresolved_ids,
            "error_ids": summary.error_ids,
            "repo_breakdown": summary.repo_breakdown,
            "source_files": summary.source_files,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)
        print(f"  ✓ Saved consolidated post-eval scorecard to: {out_path}\n")

    # 6. Automated Cleanup
    if args.clean_docker_containers or args.clean_docker_images or args.clean_cache or args.clean_all:
        if args.clean_docker_containers or args.clean_docker_images or args.clean_all:
            clean_docker_resources(args.clean_docker_containers, args.clean_docker_images, args.clean_all, args.dry_run)
        if args.clean_cache or args.clean_all:
            clean_repository_cache(args.cache_dir, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
