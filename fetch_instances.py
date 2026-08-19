#!/usr/bin/env python3
"""SWE-bench Task Instance Retrieval Utility.

Fetches, filters, inspects, and exports task instances from SWE-bench datasets
(e.g., princeton-nlp/SWE-bench_Lite, princeton-nlp/SWE-bench_Verified, princeton-nlp/SWE-bench)
using the Hugging Face `datasets` library.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_swebench_dataset(
    dataset_name: str = "princeton-nlp/SWE-bench_Lite",
    split: str = "test",
    cache_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load SWE-bench instances from Hugging Face datasets.

    Args:
        dataset_name: Name or path of the dataset on Hugging Face Hub.
        split: Dataset split ('test', 'dev', 'train').
        cache_dir: Optional custom directory to cache dataset files.

    Returns:
        List of instance dictionaries.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "Error: 'datasets' package is not installed. Please install dependencies via requirements.txt or run setup_env.sh.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading dataset '{dataset_name}' (split='{split}')...")
    dataset = load_dataset(dataset_name, split=split, cache_dir=cache_dir)
    return [dict(item) for item in dataset]


def filter_instances(
    instances: List[Dict[str, Any]],
    repo: Optional[str] = None,
    instance_ids: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Filter instances by repository, instance ID list, and limit.

    Args:
        instances: List of instance dictionaries.
        repo: Optional repository substring or exact match (e.g., 'sympy/sympy' or 'django/django').
        instance_ids: Optional explicit list of instance IDs to filter.
        limit: Optional maximum number of instances to return.

    Returns:
        Filtered list of instance dictionaries.
    """
    filtered = instances

    if repo:
        repo_lower = repo.strip().lower()
        filtered = [
            inst for inst in filtered
            if repo_lower in inst.get("repo", "").lower()
        ]

    if instance_ids:
        id_set = {i.strip() for i in instance_ids if i.strip()}
        filtered = [
            inst for inst in filtered
            if inst.get("instance_id") in id_set
        ]

    if limit is not None and limit > 0:
        filtered = filtered[:limit]

    return filtered


def export_instances(
    instances: List[Dict[str, Any]],
    output_path: Path,
    file_format: str = "jsonl",
) -> None:
    """Export filtered instances to JSON or JSONL file.

    Args:
        instances: List of instance dictionaries.
        output_path: Destination file path.
        file_format: 'jsonl' or 'json'.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if file_format == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for inst in instances:
                f.write(json.dumps(inst, ensure_ascii=False) + "\n")
    elif file_format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(instances, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"Unsupported format '{file_format}'. Must be 'jsonl' or 'json'.")

    print(f"Exported {len(instances)} instance(s) to {output_path}")


def print_summary(instances: List[Dict[str, Any]]) -> None:
    """Print human-readable summary of instances."""
    print(f"\n--- Instances Summary ({len(instances)} total) ---")
    repo_counts: Dict[str, int] = {}
    for inst in instances:
        r = inst.get("repo", "unknown")
        repo_counts[r] = repo_counts.get(r, 0) + 1

    print("Repository breakdown:")
    for r, count in sorted(repo_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {r}: {count}")

    if instances:
        print("\nFirst 5 instance IDs:")
        for inst in instances[:5]:
            print(f"  * {inst.get('instance_id')} (base commit: {inst.get('base_commit', '')[:8]})")
    print("--------------------------------------------------\n")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch and export SWE-bench task instances from Hugging Face.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        "-d",
        default="princeton-nlp/SWE-bench_Lite",
        help="Hugging Face dataset identifier (e.g. princeton-nlp/SWE-bench_Lite, princeton-nlp/SWE-bench_Verified)",
    )
    parser.add_argument(
        "--split",
        "-s",
        default="test",
        choices=["test", "dev", "train"],
        help="Dataset split to retrieve.",
    )
    parser.add_argument(
        "--repo",
        "-r",
        default=None,
        help="Filter instances by repository name (e.g. sympy/sympy, django/django).",
    )
    parser.add_argument(
        "--instance-ids",
        "-i",
        nargs="+",
        default=None,
        help="Filter by specific instance IDs (space-separated).",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit number of retrieved instances.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path to save instances (e.g., data/instances.jsonl).",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["jsonl", "json"],
        default="jsonl",
        help="Export format if --output is specified.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Display dataset summary without exporting.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    raw_instances = load_swebench_dataset(dataset_name=args.dataset, split=args.split)
    filtered = filter_instances(
        instances=raw_instances,
        repo=args.repo,
        instance_ids=args.instance_ids,
        limit=args.limit,
    )

    print_summary(filtered)

    if args.output and not args.summary_only:
        export_instances(filtered, Path(args.output), file_format=args.format)


if __name__ == "__main__":
    main()
