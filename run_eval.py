#!/usr/bin/env python3
"""
SWE-bench Evaluation Runner with Apple Silicon / ARM64 & Multi-Platform Support.

This script wraps `swebench.harness.run_evaluation` with automated pre-flight checks:
- Docker daemon status detection.
- Platform architecture detection (ARM64/Apple Silicon) to configure `--namespace ''` for local image builds.
- Predictions JSONL schema validation.
- Concurrency tuning based on available CPU cores.
- Results summarization and log navigation helpers.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def check_docker_running() -> bool:
    """Verify if the Docker daemon is accessible and responding."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("❌ Error: Docker executable not found in PATH. Please install Docker.", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print(
                "❌ Error: Docker daemon is not running or accessible.\n"
                "   Please start Docker Desktop / Docker daemon and try again.",
                file=sys.stderr,
            )
            return False
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        print(f"❌ Error checking Docker status: {e}", file=sys.stderr)
        return False


def is_arm64_or_apple_silicon() -> bool:
    """Detect if running on ARM64 (e.g. Apple Silicon M1/M2/M3/M4 or Linux aarch64)."""
    machine = platform.machine().lower()
    return machine in ("arm64", "aarch64") or (platform.system() == "Darwin" and machine != "x86_64")


def validate_predictions_file(file_path: Path) -> tuple[bool, int, List[str]]:
    """Validate that the predictions file is valid JSONL with required fields."""
    if not file_path.exists():
        return False, 0, [f"Predictions file not found: {file_path}"]

    errors = []
    valid_count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
            except json.JSONDecodeError as err:
                errors.append(f"Line {idx}: Invalid JSON syntax - {err}")
                continue

            if not isinstance(data, dict):
                errors.append(f"Line {idx}: Must be a JSON object")
                continue

            if "instance_id" not in data or not data["instance_id"]:
                errors.append(f"Line {idx}: Missing required 'instance_id' field")
            if "model_patch" not in data:
                errors.append(f"Line {idx}: Missing required 'model_patch' field")

            valid_count += 1

    return len(errors) == 0, valid_count, errors


def get_default_workers() -> int:
    """Calculate recommended default worker count based on CPU cores."""
    cpu_cnt = os.cpu_count() or 4
    # Recommend ~75% of CPUs capped at 16 for stability
    return min(max(1, int(cpu_cnt * 0.75)), 16)


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for evaluation runner."""
    parser = argparse.ArgumentParser(
        description="SWE-bench Evaluation Runner with ARM64 / Apple Silicon Support",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--dataset_name",
        type=str,
        default="princeton-nlp/SWE-bench_Lite",
        help="Dataset name or path (e.g. princeton-nlp/SWE-bench_Lite, princeton-nlp/SWE-bench, princeton-nlp/SWE-bench_Verified)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Split of the dataset to evaluate",
    )
    parser.add_argument(
        "--predictions_path",
        type=str,
        default="sample_predictions.jsonl",
        help="Path to JSONL predictions file, or 'gold' to evaluate ground truth reference patches",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=get_default_workers(),
        help="Maximum parallel Docker test evaluation containers",
    )
    parser.add_argument(
        "--run_id",
        type=str,
        default="",
        help="Unique evaluation run identifier (defaults to timestamp-based string)",
    )
    parser.add_argument(
        "--instance_ids",
        type=str,
        nargs="*",
        default=[],
        help="Specific instance ID(s) to evaluate (e.g. sympy__sympy-20590 astropy__astropy-12907)",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Docker namespace prefix. Default is '' (local build) for ARM64/Apple Silicon, or 'swebench' for x86_64",
    )
    parser.add_argument(
        "--force_local_build",
        action="store_true",
        default=False,
        help="Force local Docker image builds (equivalent to --namespace '')",
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        default="env",
        help="Docker cache level for image building and reuse",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Timeout in seconds for each test container run",
    )
    parser.add_argument(
        "--skip_validation",
        action="store_true",
        help="Skip pre-flight predictions file validation",
    )

    return parser


def run_swebench_eval(args: argparse.Namespace) -> int:
    """Execute SWE-bench harness evaluation."""
    print("=" * 70)
    print("🚀 SWE-bench Evaluation Harness Runner")
    print("=" * 70)

    # 1. Pre-flight Docker Check
    print("🔍 [1/4] Checking Docker daemon status...")
    if not check_docker_running():
        return 1
    print("  ✓ Docker daemon is active and responding.")

    # 2. Architecture & Platform Config
    is_arm = is_arm64_or_apple_silicon()
    print(f"🔍 [2/4] Detecting system architecture: {platform.machine()} ({platform.system()})")
    if is_arm:
        print("  ℹ️ Apple Silicon / ARM64 platform detected.")
        if args.namespace is None or args.force_local_build:
            # On ARM64, SWE-bench requires namespace="" to build images natively rather than pull x86 prebuilts
            args.namespace = ""
            print("  ℹ️ Configured Docker namespace: '' (Enables native ARM64 container builds)")
    else:
        if args.namespace is None:
            args.namespace = "swebench"
            print("  ℹ️ Configured Docker namespace: 'swebench' (Prebuilt x86_64 registry images)")

    # 3. Predictions Validation
    print("🔍 [3/4] Validating evaluation inputs...")
    if args.predictions_path != "gold":
        pred_path = Path(args.predictions_path).resolve()
        if not args.skip_validation:
            is_valid, count, errors = validate_predictions_file(pred_path)
            if not is_valid:
                print("❌ Prediction file validation errors:", file=sys.stderr)
                for err in errors[:10]:
                    print(f"   - {err}", file=sys.stderr)
                if len(errors) > 10:
                    print(f"   ... and {len(errors) - 10} more errors.", file=sys.stderr)
                return 1
            print(f"  ✓ Predictions file validated successfully ({count} instances found in {pred_path.name}).")
        else:
            print(f"  ℹ️ Skipping prediction file validation for {pred_path}.")
    else:
        print("  ℹ️ Evaluating 'gold' benchmark ground-truth reference patches.")

    # 4. Generate Run ID if missing
    run_id = args.run_id.strip()
    if not run_id:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        model_tag = "eval" if args.predictions_path == "gold" else Path(args.predictions_path).stem
        run_id = f"{model_tag}_{timestamp}"
    args.run_id = run_id

    print(f"🔍 [4/4] Prepared Evaluation Configuration:")
    print(f"   - Dataset:        {args.dataset_name} (split: {args.split})")
    print(f"   - Predictions:    {args.predictions_path}")
    print(f"   - Run ID:         {args.run_id}")
    print(f"   - Max Workers:    {args.max_workers}")
    print(f"   - Namespace:      '{args.namespace}'")
    print(f"   - Cache Level:    {args.cache_level}")
    print(f"   - Timeout:        {args.timeout}s")
    if args.instance_ids:
        print(f"   - Filter Instances: {', '.join(args.instance_ids)}")

    # 5. Build swebench.harness.run_evaluation command
    cmd: List[str] = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        args.dataset_name,
        "--split",
        args.split,
        "--predictions_path",
        args.predictions_path,
        "--max_workers",
        str(args.max_workers),
        "--run_id",
        args.run_id,
        "--cache_level",
        args.cache_level,
        "--timeout",
        str(args.timeout),
    ]

    if args.namespace is not None:
        cmd.extend(["--namespace", args.namespace])

    if args.instance_ids:
        cmd.append("--instance_ids")
        cmd.extend(args.instance_ids)

    print("\n" + "=" * 70)
    print("▶️ Executing SWE-bench Harness Command:")
    print(f"   {' '.join(cmd)}")
    print("=" * 70 + "\n")

    env = os.environ.copy()
    if is_arm:
        # Prevent docker buildx platform warnings
        env.setdefault("DOCKER_BUILDKIT", "1")

    try:
        process = subprocess.run(cmd, env=env)
        exit_code = process.returncode
    except KeyboardInterrupt:
        print("\n⚠️ Evaluation interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"❌ Failed to run evaluation: {exc}", file=sys.stderr)
        return 1

    print("\n" + "=" * 70)
    if exit_code == 0:
        print("✅ Evaluation run completed successfully!")
    else:
        print(f"⚠️ Evaluation finished with exit code: {exit_code}")

    print("\n📁 Output Locations:")
    print(f"   - Evaluation Run Logs: logs/run_evaluation/{args.run_id}/")
    print(f"   - Docker Build Logs:   logs/build_images/")
    print(f"   - Evaluation Report:   evaluation_results/{args.run_id}.json (if generated)")
    print("=" * 70)

    return exit_code


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    sys.exit(run_swebench_eval(args))


if __name__ == "__main__":
    main()
