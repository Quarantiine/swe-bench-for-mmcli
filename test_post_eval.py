"""Tests for post-benchmark evaluation analysis and cleanup utilities."""

import json
import os
import tempfile
from pathlib import Path
from post_eval import (
    extract_repo_from_instance_id,
    parse_evaluation_results,
    export_unresolved_instances,
    get_cache_disk_usage,
    extract_high_signal_failure_snippet,
)


def test_extract_repo_from_instance_id():
    """Verify repo string parsing from SWE-bench instance IDs."""
    assert extract_repo_from_instance_id("astropy__astropy-12907") == "astropy/astropy"
    assert extract_repo_from_instance_id("sympy__sympy-20590") == "sympy/sympy"
    assert extract_repo_from_instance_id("django__django-11001") == "django/django"
    assert extract_repo_from_instance_id("scikit-learn__scikit-learn-10297") == "scikit-learn/scikit-learn"


def test_parse_evaluation_results():
    """Verify evaluation results parsing, pass rate calculation, and repo breakdown."""
    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = Path(tmpdir) / "test.eval.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": "test_batch",
                    "total_instances": 4,
                    "submitted_instances": 4,
                    "completed_instances": 4,
                    "resolved_instances": 3,
                    "unresolved_instances": 1,
                    "error_instances": 0,
                    "empty_patch_instances": 0,
                    "submitted_ids": [
                        "astropy__astropy-12907",
                        "astropy__astropy-14182",
                        "sympy__sympy-20590",
                        "django__django-11001",
                    ],
                    "resolved_ids": [
                        "astropy__astropy-12907",
                        "astropy__astropy-14182",
                        "sympy__sympy-20590",
                    ],
                    "unresolved_ids": [
                        "django__django-11001",
                    ],
                    "error_ids": [],
                },
                f,
            )

        summary = parse_evaluation_results([report_file], extract_logs=False)
        assert summary.run_id == "test_batch"
        assert summary.total_submitted == 4
        assert summary.total_resolved == 3
        assert summary.total_unresolved == 1
        assert summary.resolution_rate_percent == 75.0
        assert "astropy/astropy" in summary.repo_breakdown
        assert summary.repo_breakdown["astropy/astropy"]["pass_rate_percent"] == 100.0
        assert summary.repo_breakdown["django/django"]["pass_rate_percent"] == 0.0


def test_export_unresolved_instances():
    """Verify exporting unresolved IDs to TXT and filtered JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = Path(tmpdir) / "eval.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": "rerun_test",
                    "submitted_ids": ["astropy__astropy-12907", "sympy__sympy-20590"],
                    "resolved_ids": ["astropy__astropy-12907"],
                    "unresolved_ids": ["sympy__sympy-20590"],
                },
                f,
            )

        src_instances = Path(tmpdir) / "test_instances.jsonl"
        with open(src_instances, "w", encoding="utf-8") as f:
            f.write(json.dumps({"instance_id": "astropy__astropy-12907", "problem_statement": "task 1"}) + "\n")
            f.write(json.dumps({"instance_id": "sympy__sympy-20590", "problem_statement": "task 2"}) + "\n")

        txt_out = Path(tmpdir) / "unresolved.txt"
        jsonl_out = Path(tmpdir) / "unresolved.jsonl"

        summary = parse_evaluation_results([report_file], extract_logs=False)
        export_unresolved_instances(
            summary,
            txt_path=str(txt_out),
            jsonl_path=str(jsonl_out),
            instances_source_path=str(src_instances),
        )

        assert txt_out.exists()
        assert txt_out.read_text().strip() == "sympy__sympy-20590"

        assert jsonl_out.exists()
        filtered_lines = [json.loads(line) for line in jsonl_out.read_text().splitlines() if line.strip()]
        assert len(filtered_lines) == 1
        assert filtered_lines[0]["instance_id"] == "sympy__sympy-20590"


def test_failure_snippet_extraction():
    """Verify log diagnostic excerpt parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        log_file.write_text(
            "Setting up testbed...\n"
            "Running pytest...\n"
            "============================= FAILURES =============================\n"
            "_____________________ test_symbol_type_error _______________________\n"
            "TypeError: name must be a string\n"
            "AssertionError: assert False\n"
            "========================= short test summary info =========================\n"
            "FAILED tests/test_symbol.py::test_symbol_type_error - TypeError\n"
        )

        snippet = extract_high_signal_failure_snippet(log_file, max_lines=5)
        assert "FAILURES" in snippet
        assert "TypeError: name must be a string" in snippet
