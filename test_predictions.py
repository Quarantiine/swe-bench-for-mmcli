"""Tests for benchmark prediction files and validation utilities."""

import json
import os
from execute_benchmark import validate_predictions, summarize_predictions


def test_sample_predictions_valid():
    """Verify that sample_predictions.jsonl exists and contains valid JSON predictions."""
    assert os.path.exists("sample_predictions.jsonl"), "sample_predictions.jsonl should exist"
    preds = validate_predictions("sample_predictions.jsonl")
    assert len(preds) > 0, "Should have at least one prediction"
    
    astropy_pred = next((p for p in preds if p.get("instance_id") == "astropy__astropy-12907"), None)
    assert astropy_pred is not None, "astropy__astropy-12907 prediction must be present"
    assert "cright[-right.shape[0]:, -right.shape[1]:] = right" in astropy_pred["model_patch"]

    astropy_rst_pred = next((p for p in preds if p.get("instance_id") == "astropy__astropy-14182"), None)
    assert astropy_rst_pred is not None, "astropy__astropy-14182 prediction must be present"
    assert "header_rows" in astropy_rst_pred["model_patch"]


def test_predictions_valid():
    """Verify that predictions.jsonl exists and contains valid JSON predictions."""
    assert os.path.exists("predictions.jsonl"), "predictions.jsonl should exist"
    preds = validate_predictions("predictions.jsonl")
    assert len(preds) > 0, "Should have at least one prediction"
    pred = preds[0]
    assert "instance_id" in pred
    assert "model_patch" in pred
    assert "model_name_or_path" in pred


def test_test_instances_valid():
    """Verify that test_instances.jsonl exists and contains valid instances."""
    if os.path.exists("test_instances.jsonl"):
        with open("test_instances.jsonl", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) > 0
        for line in lines:
            data = json.loads(line)
            assert "instance_id" in data
