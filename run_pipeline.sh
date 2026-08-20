#!/bin/bash
# ==============================================================================
# SWE-bench Lite End-to-End Evaluation Workflow Pipeline
# ==============================================================================
# This script guides the entire evaluation lifecycle:
# 1. Environment Verification & Dependency Setup
# 2. Benchmark Instance Fetching
# 3. Minovative Mind CLI Benchmark Prediction Generation
# 4. Official SWE-bench Docker Harness Evaluation
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  SWE-bench Lite Evaluation Pipeline"
echo "========================================================"

# Step 1: Check Python Virtual Environment
if [ -d "venv" ]; then
    echo "[1/4] Activating Python virtual environment..."
    source venv/bin/activate
elif [ -n "$VIRTUAL_ENV" ]; then
    echo "[1/4] Using active virtual environment: $VIRTUAL_ENV"
else
    echo "[1/4] Setting up virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Step 2: Fetch Benchmark Instances if not present
INSTANCES_FILE="${1:-test_instances.jsonl}"
if [ ! -f "$INSTANCES_FILE" ]; then
    echo "[2/4] Fetching SWE-bench Lite dataset instances..."
    python fetch_instances.py --split test --output "$INSTANCES_FILE" --limit 5
else
    echo "[2/4] Using existing instances file: $INSTANCES_FILE"
fi

# Step 3: Generate Agent Predictions using Minovative Mind CLI
PREDICTIONS_FILE="predictions.jsonl"
REPORT_FILE="evaluation_report.json"
echo "[3/4] Ready to run prediction generation..."
echo "To generate predictions and export report metrics using minovative-mind-cli, run:"
echo "  minovative-mind-cli eval -i $INSTANCES_FILE -o $PREDICTIONS_FILE -r $REPORT_FILE --autoClone"
echo ""


# Step 4: Run SWE-bench Evaluation Harness
RUN_ID="eval_$(date +%Y%m%d_%H%M%S)"
echo "[4/4] Evaluating predictions with SWE-bench harness..."
if [ -f "$PREDICTIONS_FILE" ]; then
    python run_eval.py --predictions "$PREDICTIONS_FILE" --run_id "$RUN_ID" --max_workers 2
else
    echo "Notice: Predictions file ($PREDICTIONS_FILE) not found. Using sample predictions to test harness..."
    if [ -f "sample_predictions.jsonl" ]; then
        python run_eval.py --predictions sample_predictions.jsonl --run_id "sample_test_run" --max_workers 1
    fi
fi

echo "========================================================"
echo "  Evaluation Pipeline Step Completed Successfully"
echo "========================================================"
