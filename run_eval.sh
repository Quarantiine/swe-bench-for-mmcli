#!/usr/bin/env bash
# SWE-bench Evaluation Runner Shell Script
# Wraps python run_eval.py / swebench.harness.run_evaluation
# Supports Linux, macOS, Apple Silicon (ARM64), and x86_64 architectures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
DATASET_NAME="princeton-nlp/SWE-bench_Lite"
PREDICTIONS_PATH="sample_predictions.jsonl"
MAX_WORKERS=""
RUN_ID=""
INSTANCE_IDS=""
FORCE_ARM64=false
GOLD_EVAL=false
SPLIT="test"
CACHE_LEVEL="env"
TIMEOUT="1800"

print_usage() {
    echo "SWE-bench Evaluation CLI"
    echo "Usage: ./run_eval.sh (OPTIONS)"
    echo ""
    echo "Options:"
    echo "  -p, --predictions PATH    Path to predictions JSONL file (default: sample_predictions.jsonl)"
    echo "  -g, --gold                Evaluate benchmark ground-truth reference patches"
    echo "  -d, --dataset NAME        Dataset name (default: princeton-nlp/SWE-bench_Lite)"
    echo "  -s, --split SPLIT         Dataset split (default: test)"
    echo "  -w, --workers NUM         Max parallel worker containers"
    echo "  -r, --run-id ID           Unique evaluation run identifier"
    echo "  -i, --instance-ids IDS    Space-separated list of instance IDs"
    echo "  -a, --arm64               Force ARM64 / Apple Silicon local build configuration"
    echo "  -c, --cache LEVEL         Docker build cache level (none, base, env, instance)"
    echo "  -t, --timeout SEC         Per-instance timeout in seconds (default: 1800)"
    echo "  -h, --help                Show this help message and exit"
}

# Parse CLI arguments
while test $# -gt 0; do
    case "$1" in
        (-p|--predictions)
            PREDICTIONS_PATH="$2"
            shift 2
            ;;
        (-g|--gold)
            GOLD_EVAL=true
            PREDICTIONS_PATH="gold"
            shift
            ;;
        (-d|--dataset)
            DATASET_NAME="$2"
            shift 2
            ;;
        (-s|--split)
            SPLIT="$2"
            shift 2
            ;;
        (-w|--workers)
            MAX_WORKERS="$2"
            shift 2
            ;;
        (-r|--run-id)
            RUN_ID="$2"
            shift 2
            ;;
        (-i|--instance-ids)
            INSTANCE_IDS="$2"
            shift 2
            ;;
        (-a|--arm64)
            FORCE_ARM64=true
            shift
            ;;
        (-c|--cache)
            CACHE_LEVEL="$2"
            shift 2
            ;;
        (-t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        (-h|--help)
            print_usage
            exit 0
            ;;
        (*)
            echo "Unknown argument: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Step 1: Detect and activate virtual environment if available
if test -f "$SCRIPT_DIR/venv/bin/activate"; then
    echo "Activating virtual environment from venv/..."
    . "$SCRIPT_DIR/venv/bin/activate"
elif test -f "$SCRIPT_DIR/.venv/bin/activate"; then
    echo "Activating virtual environment from .venv/..."
    . "$SCRIPT_DIR/.venv/bin/activate"
fi

# Step 2: Validate Python installation
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed or not in PATH." >&2
    exit 1
fi

# Step 3: Check Docker daemon
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running. Please start Docker and try again." >&2
    exit 1
fi

# Step 4: Assemble command line arguments
CMD_ARGS="--dataset_name $DATASET_NAME --split $SPLIT --predictions_path $PREDICTIONS_PATH --cache_level $CACHE_LEVEL --timeout $TIMEOUT"

if test -n "$MAX_WORKERS"; then
    CMD_ARGS="$CMD_ARGS --max_workers $MAX_WORKERS"
fi

if test -n "$RUN_ID"; then
    CMD_ARGS="$CMD_ARGS --run_id $RUN_ID"
fi

if test "$FORCE_ARM64" = "true"; then
    CMD_ARGS="$CMD_ARGS --force_local_build"
fi

if test -n "$INSTANCE_IDS"; then
    CMD_ARGS="$CMD_ARGS --instance_ids $INSTANCE_IDS"
fi

# Step 5: Execute Python evaluation wrapper
python3 "$SCRIPT_DIR/run_eval.py" $CMD_ARGS
