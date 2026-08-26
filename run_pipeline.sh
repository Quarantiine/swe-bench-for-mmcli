#!/usr/bin/env bash
# ==============================================================================
# SWE-bench Automated End-to-End Evaluation Pipeline
# ==============================================================================
# Purpose: Orchestrates the entire SWE-bench evaluation lifecycle:
#   1. Virtual Environment Verification & Auto-Setup (venv creation + pip install)
#   2. Benchmark Instance Fetching with Configurable Filters & Limits
#   3. Coding Agent Prediction Generation via Minovative Mind CLI
#   4. Official SWE-bench Docker Harness Evaluation with Apple Silicon/ARM64 Support
#   5. Post-Benchmark Analysis, Failure Extraction, and Resource Cleanup
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
DATASET="SWE-bench/SWE-bench_Lite"
SPLIT="test"
LIMIT=""
REPO=""
INSTANCE_IDS=""
WORKERS="2"
MAX_TURNS="1000"
TIMEOUT="60000"
INSTANCES_FILE="test_instances.jsonl"
PREDICTIONS_FILE="predictions.jsonl"
REPORT_FILE="evaluation_report.json"
RUN_ID=""
MODEL_NAME="minovative-mind-agent"
CACHE_LEVEL="env"
FORCE_ARM64=false
GOLD_EVAL=false
DRY_RUN=false
AUTO_CLONE=true
CONCURRENCY=1
VERBOSE=false
SKIP_FETCH=false
SKIP_AGENT=false
SKIP_EVAL=false
FORCE_FETCH=false
RUN_POST_EVAL=true
EXPORT_UNRESOLVED=""
EXPORT_UNRESOLVED_JSONL=""
POST_EVAL_REPORT=""
CLEAN_DOCKER=false
CLEAN_CACHE=false
CLEAN_ALL=false
MAX_FAILURES="5"
NO_LOGS=false
PYTHON_BIN="${PYTHON_BIN:-python3}"

print_usage() {
    echo "SWE-bench End-to-End Automated Pipeline"
    echo ""
    echo "Usage:"
    echo "  ./run_pipeline.sh (OPTIONS)"
    echo ""
    echo "Workflow Options & Limits:"
    echo "  -l, --limit NUM            Limit the number of benchmark instances (e.g. 2, 5, 10)"
    echo "  -r, --repo REPO            Filter instances by repository name (e.g. sympy/sympy, django/django)"
    echo "  -i, --instance-id ID       Filter by specific instance ID (e.g. sympy__sympy-20590)"
    echo "  -d, --dataset NAME         Hugging Face dataset identifier (default: SWE-bench/SWE-bench_Lite)"
    echo "  -s, --split SPLIT          Dataset split: test, dev, train (default: test)"
    echo "  -w, --workers NUM          Maximum parallel Docker evaluation workers (default: 2)"
    echo "  -m, --max-turns NUM        Maximum agent execution turns per instance (default: 30)"
    echo "  -t, --timeout SEC          Per-instance evaluation timeout in seconds (default: 1800)"
    echo ""
    echo "File & Identifier Paths:"
    echo "  -f, --instances PATH       Path to instances JSONL file (default: test_instances.jsonl)"
    echo "  -p, --predictions PATH     Path to predictions JSONL file (default: predictions.jsonl)"
    echo "      --report PATH          Path to export evaluation report JSON (default: evaluation_report.json)"
    echo "      --run-id ID            Custom run identifier for evaluation logs (default: auto-generated)"
    echo "      --model NAME           Model name tag for prediction metadata (default: minovative-mind-agent)"
    echo ""
    echo "Pipeline Stage Execution Controls:"
    echo "      --skip-fetch           Skip instance retrieval (use existing instances file)"
    echo "      --skip-agent           Skip agent prediction generation (use existing predictions file)"
    echo "      --skip-eval            Skip Docker harness evaluation step"
    echo "      --skip-post-eval       Skip post-evaluation analysis & scorecard generation"
    echo "      --post-eval            Explicitly enable post-evaluation analysis step (default: enabled)"
    echo "      --force-fetch          Force re-fetching instances from Hugging Face"
    echo "      --dry-run              Dry run mode for agent predictions (no LLM calls)"
    echo "      --no-auto-clone        Disable automatic Git repository cloning during agent run"
    echo "  -c, --concurrency NUM      Number of instances for agent to evaluate concurrently (default: 1)"
    echo "  -a, --arm64                Force ARM64 / Apple Silicon local container build settings"
    echo "  -g, --gold                 Evaluate benchmark ground-truth reference patches directly"
    echo "  -v, --verbose              Enable verbose logging"
    echo ""
    echo "Post-Benchmark Analysis & Cleanup Hooks:"
    echo "  -u, --export-unresolved PATH Export unresolved/failed instance IDs to text file"
    echo "  -j, --export-jsonl PATH      Export unresolved instances as filtered JSONL for iteration"
    echo "      --post-eval-report PATH  Save consolidated post-eval scorecard to JSON file"
    echo "      --max-failures NUM       Maximum failure logs to display in terminal (default: 5)"
    echo "      --no-logs                Skip failure log extraction in post-eval summary"
    echo "      --clean-docker           Remove test containers & Docker images after benchmark"
    echo "      --clean-cache            Clear SWE-bench git repo cache (~/.cache/swe-bench-repos)"
    echo "      --clean-all, --prune     Full cleanup of Docker images, containers & repo cache"
    echo "  -h, --help                 Display this help message and exit"
    echo ""
    echo "Examples:"
    echo "  # Run pilot evaluation with 2 instances:"
    echo "  ./run_pipeline.sh --limit 2"
    echo ""
    echo "  # Run on SymPy repository instances with 4 workers:"
    echo "  ./run_pipeline.sh --repo sympy/sympy --limit 5 --workers 4"
    echo ""
    echo "  # Run specific instance end-to-end:"
    echo "  ./run_pipeline.sh --instance-id sympy__sympy-20590"
    echo ""
    echo "  # Run SWE-bench Verified dataset with 50 turns per instance:"
    echo "  ./run_pipeline.sh --dataset SWE-bench/SWE-bench_Verified --limit 10 --max-turns 50"
    echo ""
    echo "  # Run evaluation, export unresolved tasks to JSONL, and clean Docker images:"
    echo "  ./run_pipeline.sh --limit 5 -j failed_tasks.jsonl --clean-docker"
}

# Parse CLI arguments
while test $# -gt 0; do
    case "$1" in
        (-l|--limit)
            LIMIT="$2"
            shift 2
            ;;
        (-r|--repo)
            REPO="$2"
            shift 2
            ;;
        (-i|--instance-id|--instance-ids|--instance_id)
            if test -n "$INSTANCE_IDS"; then
                INSTANCE_IDS="$INSTANCE_IDS $2"
            else
                INSTANCE_IDS="$2"
            fi
            shift 2
            ;;
        (-d|--dataset|--dataset-name|--dataset_name)
            DATASET="$2"
            shift 2
            ;;
        (-s|--split)
            SPLIT="$2"
            shift 2
            ;;
        (-w|--workers|--max-workers|--max_workers)
            WORKERS="$2"
            shift 2
            ;;
        (-m|--max-turns|--max_turns)
            MAX_TURNS="$2"
            shift 2
            ;;
        (-t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        (-f|--instances|--instances-file)
            INSTANCES_FILE="$2"
            shift 2
            ;;
        (-p|--predictions|--predictions-file)
            PREDICTIONS_FILE="$2"
            shift 2
            ;;
        (--report|--report-file)
            REPORT_FILE="$2"
            shift 2
            ;;
        (--run-id|--run_id)
            RUN_ID="$2"
            shift 2
            ;;
        (--model|--model-name)
            MODEL_NAME="$2"
            shift 2
            ;;
        (--cache|--cache-level|--cache_level)
            CACHE_LEVEL="$2"
            shift 2
            ;;
        (-a|--arm64)
            FORCE_ARM64=true
            shift
            ;;
        (-g|--gold)
            GOLD_EVAL=true
            PREDICTIONS_FILE="gold"
            SKIP_AGENT=true
            shift
            ;;
        (--dry-run|--dryRun)
            DRY_RUN=true
            shift
            ;;
        (--no-auto-clone)
            AUTO_CLONE=false
            shift
            ;;
        (-c|--concurrency)
            CONCURRENCY="$2"
            shift 2
            ;;
        (--skip-fetch)
            SKIP_FETCH=true
            shift
            ;;
        (--skip-agent)
            SKIP_AGENT=true
            shift
            ;;
        (--skip-eval)
            SKIP_EVAL=true
            shift
            ;;
        (--skip-post-eval|--no-post-eval|--skip_post_eval)
            RUN_POST_EVAL=false
            shift
            ;;
        (--post-eval|--post_eval)
            RUN_POST_EVAL=true
            shift
            ;;
        (-u|--export-unresolved|--export_unresolved|--unresolved)
            EXPORT_UNRESOLVED="$2"
            shift 2
            ;;
        (-j|--export-jsonl|--export-unresolved-jsonl|--export_unresolved_jsonl)
            EXPORT_UNRESOLVED_JSONL="$2"
            shift 2
            ;;
        (--post-eval-report|--post_eval_report)
            POST_EVAL_REPORT="$2"
            shift 2
            ;;
        (--max-failures|--max_failures)
            MAX_FAILURES="$2"
            shift 2
            ;;
        (--no-logs|--no_logs)
            NO_LOGS=true
            shift
            ;;
        (--clean-docker|--clean_docker)
            CLEAN_DOCKER=true
            shift
            ;;
        (--clean-cache|--clean_cache)
            CLEAN_CACHE=true
            shift
            ;;
        (--clean-all|--clean_all|--prune)
            CLEAN_ALL=true
            shift
            ;;
        (--force-fetch)
            FORCE_FETCH=true
            shift
            ;;
        (-v|--verbose)
            VERBOSE=true
            shift
            ;;
        (-h|--help)
            print_usage
            exit 0
            ;;
        (*)
            if test -n "$1" && test ! -f "$INSTANCES_FILE"; then
                INSTANCES_FILE="$1"
                shift
            else
                echo "Error: Unknown argument '$1'"
                print_usage
                exit 1
            fi
            ;;
    esac
done

# Map Hugging Face namespace aliases if needed
case "$DATASET" in
    (princeton-nlp/SWE-bench_Lite)
        DATASET="SWE-bench/SWE-bench_Lite"
        ;;
    (princeton-nlp/SWE-bench_Verified)
        DATASET="SWE-bench/SWE-bench_Verified"
        ;;
    (princeton-nlp/SWE-bench)
        DATASET="SWE-bench/SWE-bench"
        ;;
    (*)
        ;;
esac

echo "================================================================"
echo "  SWE-bench Automated Benchmark & Evaluation Pipeline"
echo "================================================================"
echo "Configuration Profile:"
echo "  - Dataset:            ${DATASET} (split: ${SPLIT})"
if test -n "$LIMIT"; then
    echo "  - Instance Limit:     ${LIMIT}"
fi
if test -n "$REPO"; then
    echo "  - Repository Filter:  ${REPO}"
fi
if test -n "$INSTANCE_IDS"; then
    echo "  - Specific ID(s):     ${INSTANCE_IDS}"
fi
echo "  - Instances File:     ${INSTANCES_FILE}"
echo "  - Predictions File:   ${PREDICTIONS_FILE}"
echo "  - Report File:        ${REPORT_FILE}"
echo "  - Agent Max Turns:    ${MAX_TURNS}"
echo "  - Evaluation Workers: ${WORKERS}"
echo "  - Timeout:            ${TIMEOUT}s"
echo "================================================================"
echo ""

# Step 1: Virtual Environment Verification & Auto-Setup
echo "(Step 1/5) Verifying Python Virtual Environment..."

VENV_PATH=""
if test -d "$SCRIPT_DIR/venv"; then
    VENV_PATH="$SCRIPT_DIR/venv"
elif test -d "$SCRIPT_DIR/.venv"; then
    VENV_PATH="$SCRIPT_DIR/.venv"
elif test -n "${VIRTUAL_ENV:-}" && test -d "$VIRTUAL_ENV"; then
    VENV_PATH="$VIRTUAL_ENV"
fi

if test -z "$VENV_PATH"; then
    echo "  No existing virtual environment detected. Initializing venv at ./venv..."
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        echo "  Error: Python binary '${PYTHON_BIN}' not found. Please install Python 3.9+." >&2
        exit 1
    fi
    "$PYTHON_BIN" -m venv "$SCRIPT_DIR/venv"
    VENV_PATH="$SCRIPT_DIR/venv"
fi

# Activate virtual environment
source "${VENV_PATH}/bin/activate"
PYTHON_EXEC="${VENV_PATH}/bin/python"

# Verify dependencies in venv
NEEDS_INSTALL=false
if ! "$PYTHON_EXEC" -c "import datasets, swebench, docker" >/dev/null 2>&1; then
    NEEDS_INSTALL=true
fi

if test "$NEEDS_INSTALL" = "true"; then
    echo "  Installing/updating required packages from requirements.txt..."
    "$PYTHON_EXEC" -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
    if test -f "$SCRIPT_DIR/requirements.txt"; then
        "$PYTHON_EXEC" -m pip install -r "$SCRIPT_DIR/requirements.txt"
    else
        echo "  Error: requirements.txt not found at $SCRIPT_DIR/requirements.txt" >&2
        exit 1
    fi
fi

PYTHON_VER=$("$PYTHON_EXEC" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
echo "  Virtual environment active: ${VENV_PATH} (Python ${PYTHON_VER})"
echo ""

# Step 2: Fetch Benchmark Instances
echo "(Step 2/5) Preparing Benchmark Instances..."

FETCH_REQUIRED=false
if test "$FORCE_FETCH" = "true"; then
    FETCH_REQUIRED=true
elif test ! -f "$INSTANCES_FILE"; then
    FETCH_REQUIRED=true
elif test "$SKIP_FETCH" = "false" && { test -n "$LIMIT" || test -n "$REPO" || test -n "$INSTANCE_IDS"; }; then
    FETCH_REQUIRED=true
fi

if test "$FETCH_REQUIRED" = "true" && test "$SKIP_FETCH" = "false"; then
    echo "  Fetching instances from ${DATASET} (split: ${SPLIT})..."
    
    FETCH_ARGS="--dataset $DATASET --split $SPLIT --output $INSTANCES_FILE --format jsonl"
    if test -n "$LIMIT"; then
        FETCH_ARGS="$FETCH_ARGS --limit $LIMIT"
    fi
    if test -n "$REPO"; then
        FETCH_ARGS="$FETCH_ARGS --repo $REPO"
    fi
    if test -n "$INSTANCE_IDS"; then
        FETCH_ARGS="$FETCH_ARGS --instance-ids $INSTANCE_IDS"
    fi

    "$PYTHON_EXEC" "$SCRIPT_DIR/fetch_instances.py" $FETCH_ARGS
    echo "  Saved instance tasks to: ${INSTANCES_FILE}"
else
    if test -f "$INSTANCES_FILE"; then
        INST_COUNT=$(wc -l < "$INSTANCES_FILE" | tr -d ' ')
        echo "  Using existing instance file: ${INSTANCES_FILE} (${INST_COUNT} instances)"
    else
        echo "  Error: Instance file '${INSTANCES_FILE}' not found and fetch is disabled." >&2
        exit 1
    fi
fi
echo ""

# Step 3: Agent Prediction Generation via Minovative Mind CLI
echo "(Step 3/5) Agent Benchmark Prediction Generation..."

# Find Minovative Mind CLI runner
MMCLI_EXEC=""
MMCLI_IS_NODE=false

if test -n "${MMCLI_BIN:-}" && test -x "$MMCLI_BIN"; then
    MMCLI_EXEC="$MMCLI_BIN"
elif command -v minovative-mind-cli >/dev/null 2>&1; then
    MMCLI_EXEC="minovative-mind-cli"
elif test -f "$SCRIPT_DIR/../../Work Projects/minovative-mind-cli/bin/run.js"; then
    MMCLI_EXEC="$SCRIPT_DIR/../../Work Projects/minovative-mind-cli/bin/run.js"
    MMCLI_IS_NODE=true
elif test -f "$SCRIPT_DIR/../minovative-mind-cli/bin/run.js"; then
    MMCLI_EXEC="$SCRIPT_DIR/../minovative-mind-cli/bin/run.js"
    MMCLI_IS_NODE=true
fi

if test "$SKIP_AGENT" = "true"; then
    echo "  Skipping agent prediction generation step as requested."
elif test "$GOLD_EVAL" = "true"; then
    echo "  Gold evaluation requested: Bypassing agent prediction generation."
elif test -n "$MMCLI_EXEC"; then
    echo "  Invoking Minovative Mind CLI evaluation runner..."
    
    AGENT_TIMEOUT_MS=$((TIMEOUT * 1000))
    AGENT_ARGS="eval -i $INSTANCES_FILE -o $PREDICTIONS_FILE -r $REPORT_FILE -m $MODEL_NAME --maxTurns $MAX_TURNS --timeout $AGENT_TIMEOUT_MS -c $CONCURRENCY"
    
    if test "$AUTO_CLONE" = "true"; then
        AGENT_ARGS="$AGENT_ARGS --autoClone"
    fi
    if test "$DRY_RUN" = "true"; then
        AGENT_ARGS="$AGENT_ARGS --dryRun"
    fi
    if test "$VERBOSE" = "true"; then
        AGENT_ARGS="$AGENT_ARGS -v"
    fi
    if test -n "$REPO"; then
        AGENT_ARGS="$AGENT_ARGS --repo $REPO"
    fi
    if test -n "$LIMIT"; then
        AGENT_ARGS="$AGENT_ARGS --limit $LIMIT"
    fi
    if test -n "$INSTANCE_IDS"; then
        for first_id in $INSTANCE_IDS; do
            AGENT_ARGS="$AGENT_ARGS --instanceId $first_id"
            break
        done
    fi

    if test "$MMCLI_IS_NODE" = "true"; then
        echo "  Command: node \"$MMCLI_EXEC\" ${AGENT_ARGS}"
        node "$MMCLI_EXEC" $AGENT_ARGS
    else
        echo "  Command: \"$MMCLI_EXEC\" ${AGENT_ARGS}"
        "$MMCLI_EXEC" $AGENT_ARGS
    fi
    
    echo "  Agent predictions written to: ${PREDICTIONS_FILE}"
else
    echo "  Notice: 'minovative-mind-cli' executable not found in PATH or adjacent directories."
    if test -f "$PREDICTIONS_FILE"; then
        echo "  Found existing predictions file: ${PREDICTIONS_FILE}"
    else
        echo "  To generate predictions manually with the CLI, run:"
        echo "    minovative-mind-cli eval -i ${INSTANCES_FILE} -o ${PREDICTIONS_FILE} -r ${REPORT_FILE} --autoClone"
        if test -f "sample_predictions.jsonl"; then
            echo "  Falling back to 'sample_predictions.jsonl' for evaluation pipeline testing."
            PREDICTIONS_FILE="sample_predictions.jsonl"
        fi
    fi
fi
echo ""
# Step 4: SWE-bench Docker Harness Evaluation
echo "(Step 4/5) SWE-bench Docker Harness Evaluation..."

if test "$SKIP_EVAL" = "true"; then
    echo "  Skipping Docker evaluation harness step as requested."
else
    # Check Docker daemon availability
    if ! docker info >/dev/null 2>&1; then
        echo "  Error: Docker daemon is not accessible or not running." >&2
        echo "  Please start Docker Desktop or your Docker service and re-run." >&2
        exit 1
    fi

    EVAL_TARGET="${PREDICTIONS_FILE}"
    if test "$GOLD_EVAL" = "true"; then
        EVAL_TARGET="gold"
    elif test ! -f "$EVAL_TARGET"; then
        if test -f "sample_predictions.jsonl"; then
            echo "  Target predictions file '${EVAL_TARGET}' not found. Using 'sample_predictions.jsonl'..."
            EVAL_TARGET="sample_predictions.jsonl"
        else
            echo "  Error: No predictions file found to evaluate at '${EVAL_TARGET}'." >&2
            exit 1
        fi
    fi

    # Generate Run ID if not specified
    if test -z "$RUN_ID"; then
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        TARGET_STEM="eval"
        if test "$EVAL_TARGET" != "gold"; then
            TARGET_STEM=$(basename "$EVAL_TARGET" .jsonl)
        fi
        RUN_ID="${TARGET_STEM}_${TIMESTAMP}"
    fi

    # Detect platform architecture for Docker emulation / local build
    ARCH="$(uname -m)"
    if test "$ARCH" = "arm64" || test "$ARCH" = "aarch64" || test "$FORCE_ARM64" = "true"; then
        export DOCKER_DEFAULT_PLATFORM="linux/amd64"
        export DOCKER_BUILDKIT="1"
    fi

    EVAL_ARGS="--dataset_name $DATASET --split $SPLIT --predictions_path $EVAL_TARGET --max_workers $WORKERS --run_id $RUN_ID --cache_level $CACHE_LEVEL --timeout $TIMEOUT"
    if test "$FORCE_ARM64" = "true"; then
        EVAL_ARGS="$EVAL_ARGS --force_local_build"
    fi
    if test -n "$INSTANCE_IDS"; then
        EVAL_ARGS="$EVAL_ARGS --instance_ids $INSTANCE_IDS"
    fi

    echo "  Running SWE-bench official test harness evaluation (${RUN_ID})..."
    "$PYTHON_EXEC" "$SCRIPT_DIR/run_eval.py" $EVAL_ARGS

    if test -f "$SCRIPT_DIR/evaluation_results/${RUN_ID}.json"; then
        echo ""
        echo "  Evaluation results recorded in: evaluation_results/${RUN_ID}.json"
    fi
fi
echo ""

# Step 5: Post-Benchmark Analysis, Failure Extraction, and Resource Cleanup
echo "(Step 5/5) Post-Benchmark Analysis & Diagnostics..."

if test "$RUN_POST_EVAL" = "false"; then
    echo "  Skipping post-benchmark analysis as requested (--skip-post-eval)."
else
    POST_EVAL_SCRIPT="$SCRIPT_DIR/post_eval.py"
    if test -f "$POST_EVAL_SCRIPT"; then
        POST_ARGS=()
        if test -n "$RUN_ID"; then
            POST_ARGS+=(--run-id "$RUN_ID")
        fi
        if test -f "$REPORT_FILE"; then
            POST_ARGS+=(--agent-report "$REPORT_FILE")
        fi
        if test -f "$INSTANCES_FILE"; then
            POST_ARGS+=(--instances-source "$INSTANCES_FILE")
        fi
        if test -n "$EXPORT_UNRESOLVED"; then
            POST_ARGS+=(--export-unresolved "$EXPORT_UNRESOLVED")
        fi
        if test -n "$EXPORT_UNRESOLVED_JSONL"; then
            POST_ARGS+=(--export-unresolved-jsonl "$EXPORT_UNRESOLVED_JSONL")
        fi
        if test -n "$POST_EVAL_REPORT"; then
            POST_ARGS+=(--output-summary "$POST_EVAL_REPORT")
        fi
        if test -n "$MAX_FAILURES"; then
            POST_ARGS+=(--max-failures "$MAX_FAILURES")
        fi
        if test "$NO_LOGS" = "true"; then
            POST_ARGS+=(--no-logs)
        fi
        if test "$CLEAN_ALL" = "true"; then
            POST_ARGS+=(--clean-all)
        else
            if test "$CLEAN_DOCKER" = "true"; then
                POST_ARGS+=(--clean-docker-containers --clean-docker-images)
            fi
            if test "$CLEAN_CACHE" = "true"; then
                POST_ARGS+=(--clean-cache)
            fi
        fi
        if test "$DRY_RUN" = "true"; then
            POST_ARGS+=(--dry-run)
        fi

        "$PYTHON_EXEC" "$POST_EVAL_SCRIPT" "${POST_ARGS[@]}"
    else
        echo "  Notice: post_eval.py not found at $POST_EVAL_SCRIPT"
    fi
fi

echo ""
echo "================================================================"
echo "  Pipeline Execution Completed Successfully!"
echo "================================================================"
