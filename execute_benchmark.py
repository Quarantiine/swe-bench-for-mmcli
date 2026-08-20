#!/usr/bin/env python3
"""
SWE-bench Lite Evaluation Flow Helper CLI.

Validates predictions, computes summary stats, and orchestrates evaluation runs.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Any


def validate_predictions(predictions_path: str) -> List[Dict[str, Any]]:
    """Validate prediction JSONL structure against SWE-bench specification."""
    if not os.path.exists(predictions_path):
        print(f"Error: Predictions file not found: {predictions_path}", file=sys.stderr)
        sys.exit(1)

    valid_predictions = []
    required_keys = {"instance_id", "model_patch"}
    
    with open(predictions_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as err:
                print(f"Error on line {idx}: Invalid JSON: {err}", file=sys.stderr)
                continue

            missing = required_keys - set(data.keys())
            if missing:
                print(f"Warning on line {idx}: Missing required fields: {missing}", file=sys.stderr)
            
            valid_predictions.append(data)

    return valid_predictions


def summarize_predictions(predictions: List[Dict[str, Any]]) -> None:
    """Print statistical breakdown of predictions."""
    total = len(predictions)
    with_patches = [p for p in predictions if (p.get("model_patch") or "").strip()]
    empty_patches = total - len(with_patches)

    print("\n" + "=" * 60)
    print("  PREDICTIONS FILE SUMMARY")
    print("=" * 60)
    print(f"Total Predictions Loaded : {total}")
    print(f"Patches Present          : {len(with_patches)} ({len(with_patches) / max(total, 1) * 100:.1f}%)")
    print(f"Empty/Missing Patches    : {empty_patches}")
    
    if with_patches:
        avg_len = sum(len(p.get("model_patch", "")) for p in with_patches) / len(with_patches)
        print(f"Average Patch Size       : {avg_len:.0f} bytes")

    print("=" * 60 + "\n")


def aggregate_reports(report_paths: List[str], output_path: str = None) -> Dict[str, Any]:
    """Combine multiple evaluation run JSON reports into a single consolidated summary."""
    total_submitted = 0
    total_completed = 0
    resolved_ids = set()
    unresolved_ids = set()
    error_ids = set()
    completed_ids = set()
    repo_stats: Dict[str, Dict[str, int]] = {}

    for path in report_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to read report {path}: {e}", file=sys.stderr)
            continue

        submitted = data.get("submitted_ids", [])
        total_submitted += len(submitted)
        
        for inst_id in data.get("resolved_ids", []):
            resolved_ids.add(inst_id)
            repo = inst_id.split("__")[0]
            repo_stats.setdefault(repo, {"submitted": 0, "resolved": 0})
            repo_stats[repo]["resolved"] += 1

        for inst_id in data.get("unresolved_ids", []):
            unresolved_ids.add(inst_id)

        for inst_id in data.get("error_ids", []):
            error_ids.add(inst_id)

        for inst_id in data.get("completed_ids", []):
            completed_ids.add(inst_id)

        for inst_id in submitted:
            repo = inst_id.split("__")[0]
            repo_stats.setdefault(repo, {"submitted": 0, "resolved": 0})
            repo_stats[repo]["submitted"] += 1

    total_unique_submitted = len(completed_ids.union(unresolved_ids).union(error_ids)) or total_submitted
    total_unique_resolved = len(resolved_ids)
    pass_rate = (total_unique_resolved / max(total_unique_submitted, 1)) * 100

    print("\n" + "=" * 65)
    print("  🏆 SWE-BENCH CONSOLIDATED BENCHMARK SCORECARD")
    print("=" * 65)
    print(f"Total Unique Instances Evaluated : {total_unique_submitted}")
    print(f"Successfully Resolved Tasks      : {total_unique_resolved}")
    print(f"Overall Benchmark Pass Rate       : {pass_rate:.1f}%")
    print("-" * 65)
    print("  PER-REPOSITORY BREAKDOWN:")
    print(f"  {'Repository':<25} {'Resolved':<10} {'Total':<10} {'Rate (%)'}")
    print("  " + "-" * 55)
    for repo, stats in sorted(repo_stats.items()):
        r_sub = stats["submitted"]
        r_res = stats["resolved"]
        r_rate = (r_res / max(r_sub, 1)) * 100
        print(f"  {repo:<25} {r_res:<10} {r_sub:<10} {r_rate:>6.1f}%")
    print("=" * 65 + "\n")

    summary = {
        "total_submitted": total_unique_submitted,
        "total_resolved": total_unique_resolved,
        "pass_rate_percent": round(pass_rate, 2),
        "resolved_ids": sorted(list(resolved_ids)),
        "unresolved_ids": sorted(list(unresolved_ids)),
        "error_ids": sorted(list(error_ids)),
        "repo_breakdown": repo_stats,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4)
        print(f"Saved aggregated scorecard to: {output_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="SWE-bench Lite Execution Flow & Validation Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Validate subcommand
    val_parser = subparsers.add_parser("validate", help="Validate a predictions JSONL file")
    val_parser.add_argument("--predictions", "-p", required=True, help="Path to predictions.jsonl file")

    # Run pipeline subcommand
    run_parser = subparsers.add_parser("run", help="Run full evaluation harness on predictions")
    run_parser.add_argument("--predictions", "-p", required=True, help="Path to predictions.jsonl file")
    run_parser.add_argument("--run_id", "-r", default="eval_run", help="Unique evaluation run identifier")
    run_parser.add_argument("--dataset", "-d", default="SWE-bench/SWE-bench_Lite", help="Benchmark dataset")
    run_parser.add_argument("--max_workers", "-w", type=int, default=2, help="Parallel evaluation workers")

    # Merge/Report subcommand
    merge_parser = subparsers.add_parser("report", help="Aggregate multiple evaluation batch reports into one scoreboard")
    merge_parser.add_argument("reports", nargs="+", help="Paths to evaluation JSON report files (e.g. *.eval.json)")
    merge_parser.add_argument("--output", "-o", default="benchmark_summary.json", help="Path to save merged summary JSON")

    args = parser.parse_args()

    if args.command == "validate":
        preds = validate_predictions(args.predictions)
        summarize_predictions(preds)
    elif args.command == "run":
        preds = validate_predictions(args.predictions)
        summarize_predictions(preds)
        from run_eval import run_evaluation
        run_evaluation(
            predictions_path=args.predictions,
            run_id=args.run_id,
            dataset_name=args.dataset,
            max_workers=args.max_workers,
        )
    elif args.command == "report":
        aggregate_reports(args.reports, args.output)


if __name__ == "__main__":
    main()
