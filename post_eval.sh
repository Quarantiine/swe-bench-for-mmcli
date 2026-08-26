#!/usr/bin/env bash
# ==============================================================================
# SWE-bench Post-Benchmark Analysis & Cleanup Runner
# ==============================================================================
# Purpose: Orchestrates post-benchmark workflows:
#   1. Consolidates test harness results and agent prediction economics
#   2. Extracts diagnostic failure logs, failed test names, and tracebacks
#   3. Calculates per-repository and overall resolution rates
#   4. Exports unresolved instances for targeted re-runs (TXT or JSONL)
#   5. Automates Docker container/image pruning and repository disk cache cleanup
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
RUN_ID=""
EVAL_REPORTS=()
AGENT_REPORT=""
OUTPUT_SUMMARY=""
EXPORT_UNRESOLVED=""
EXPORT_UNRESOLVED_JSONL=""
INSTANCES_SOURCE="test_instances.jsonl"
JSON_OUTPUT=false
NO_LOGS=false
CLEAN_DOCKER_CONTAINERS=false
CLEAN_DOCKER_IMAGES=false
CLEAN_CACHE=false
CLEAN_ALL=false
DRY_RUN=false
MAX_FAILURES="5"
PYTHON_BIN="${PYTHON_BIN:-python3}"

print_usage() {
    echo "=============================================================================="
    echo "SWE-bench Post-Benchmark Analysis & Cleanup Runner"
    echo "=============================================================================="
    echo ""
    echo "Usage:"
    echo "  ./post_eval.sh (OPTIONS)"
    echo ""
    echo "Report & Run Identification:"
    echo "  -r, --run-id ID               Evaluation run ID to locate results and logs"
    echo "  -e, --report PATH             Path to evaluation JSON result file or glob (e.g. *.eval.json)"
    echo "      --agent-report PATH       Path to agent report JSON (default: evaluation_report.json)"
    echo "      --no-logs                 Skip diagnostic failure log snippet extraction"
    echo "      --max-failures NUM        Maximum number of failure logs to display (default: 5)"
    echo ""
    echo "Export & Iteration Options:"
    echo "  -u, --export-unresolved PATH  Export failed/unresolved instance IDs to text file"
    echo "  -j, --export-jsonl PATH       Export unresolved instances as filtered JSONL"
    echo "  -s, --instances-source PATH   Source instances JSONL to filter (default: test_instances.jsonl)"
    echo "  -o, --output-summary PATH     Save consolidated scorecard to JSON file"
    echo "      --json                    Output raw scorecard JSON to stdout"
    echo ""
    echo "Cleanup & Disk Space Recovery:"
    echo "      --clean-docker            Remove stopped test containers & evaluation images"
    echo "      --clean-cache             Clear SWE-bench git repo cache (~/.cache/swe-bench-repos)"
    echo "      --clean-all, --prune      Complete cleanup of all Docker images, containers & cache"
    echo "      --dry-run                 Simulate cleanup without deleting resources"
    echo ""
    echo "General Options:"
    echo "  -h, --help                    Display this help message and exit"
    echo ""
    echo "Examples:"
    echo "  # Run post-evaluation analysis on latest run:"
    echo "  ./post_eval.sh"
    echo ""
    echo "  # Analyze a specific evaluation run ID and export unresolved tasks:"
    echo "  ./post_eval.sh --run-id pilot_eval -u unresolved_tasks.txt"
    echo ""
    echo "  # Filter source instances for re-running failed tasks:"
    echo "  ./post_eval.sh --export-jsonl failed_instances.jsonl --instances-source test_instances.jsonl"
    echo ""
    echo "  # Generate scorecard and clean all Docker/repo cache:"
    echo "  ./post_eval.sh --clean-all"
    echo "=============================================================================="
}

# Parse command-line arguments
while test $# -gt 0; do
    case "$1" in
        (-r|--run-id|--run_id)
            RUN_ID="$2"
            shift 2
            ;;
        (-e|--report|--eval-report|--eval_report)
            EVAL_REPORTS+=("$2")
            shift 2
            ;;
        (--agent-report|--agent_report)
            AGENT_REPORT="$2"
            shift 2
            ;;
        (-o|--output-summary|--output_summary|--output)
            OUTPUT_SUMMARY="$2"
            shift 2
            ;;
        (-u|--export-unresolved|--export_unresolved|--unresolved)
            EXPORT_UNRESOLVED="$2"
            shift 2
            ;;
        (-j|--export-jsonl|--export-unresolved-jsonl|--export_unresolved_jsonl)
            EXPORT_UNRESOLVED_JSONL="$2"
            shift 2
            ;;
        (-s|--instances-source|--instances_source)
            INSTANCES_SOURCE="$2"
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
        (--json)
            JSON_OUTPUT=true
            shift
            ;;
        (--clean-docker|--clean_docker)
            CLEAN_DOCKER_CONTAINERS=true
            CLEAN_DOCKER_IMAGES=true
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
        (--dry-run|--dry_run)
            DRY_RUN=true
            shift
            ;;
        (-h|--help)
            print_usage
            exit 0
            ;;
        (*)
            echo "❌ Unknown argument: $1" >&2
            echo "Run './post_eval.sh --help' for usage instructions." >&2
            exit 1
            ;;
    esac
done

# Step 1: Detect and Activate Python Virtual Environment
if test -f "venv/bin/activate"; then
    source "venv/bin/activate"
    PYTHON_BIN="venv/bin/python"
elif test -f ".venv/bin/activate"; then
    source ".venv/bin/activate"
    PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "❌ Error: Python not found in system PATH or virtual environment." >&2
    exit 1
fi

# Step 2: Build Arguments for post_eval.py
PY_ARGS=()

if test -n "$RUN_ID"; then
    PY_ARGS+=(--run-id "$RUN_ID")
fi

if test ${#EVAL_REPORTS[@]} -gt 0; then
    for rep in "${EVAL_REPORTS[@]}"; do
        PY_ARGS+=(--report "$rep")
    done
fi

if test -n "$AGENT_REPORT"; then
    PY_ARGS+=(--agent-report "$AGENT_REPORT")
fi

if test -n "$OUTPUT_SUMMARY"; then
    PY_ARGS+=(--output-summary "$OUTPUT_SUMMARY")
fi

if test -n "$EXPORT_UNRESOLVED"; then
    PY_ARGS+=(--export-unresolved "$EXPORT_UNRESOLVED")
fi

if test -n "$EXPORT_UNRESOLVED_JSONL"; then
    PY_ARGS+=(--export-unresolved-jsonl "$EXPORT_UNRESOLVED_JSONL")
fi

if test -n "$INSTANCES_SOURCE"; then
    PY_ARGS+=(--instances-source "$INSTANCES_SOURCE")
fi

if test "$NO_LOGS" = "true"; then
    PY_ARGS+=(--no-logs)
fi

if test -n "$MAX_FAILURES"; then
    PY_ARGS+=(--max-failures "$MAX_FAILURES")
fi

if test "$JSON_OUTPUT" = "true"; then
    PY_ARGS+=(--json)
fi

if test "$CLEAN_ALL" = "true"; then
    PY_ARGS+=(--clean-all)
else
    if test "$CLEAN_DOCKER_CONTAINERS" = "true"; then
        PY_ARGS+=(--clean-docker-containers)
    fi
    if test "$CLEAN_DOCKER_IMAGES" = "true"; then
        PY_ARGS+=(--clean-docker-images)
    fi
    if test "$CLEAN_CACHE" = "true"; then
        PY_ARGS+=(--clean-cache)
    fi
fi

if test "$DRY_RUN" = "true"; then
    PY_ARGS+=(--dry-run)
fi

# Step 3: Execute post_eval.py
exec "$PYTHON_BIN" post_eval.py "${PY_ARGS[@]}"
