# SWE-bench Evaluation Harness & Benchmark Suite

An automated evaluation framework and benchmarking suite for **SWE-bench** (Lite, Full, and Verified), specifically optimized for automated coding agents, continuous benchmarking, and local reproduction with cross-platform support including **Apple Silicon (M-series ARM64)** and Linux/x86_64.

---

## 📋 Table of Contents

1. [Overview](#-overview)
2. [Prerequisites & System Requirements](#-prerequisites--system-requirements)
3. [⚡ Quick Command Reference & Cheat Sheet](#-quick-command-reference--cheat-sheet)
4. [Step-by-Step Execution Workflow](#-step-by-step-execution-workflow)
5. [Quick Start & Environment Setup](#-quick-start--environment-setup)
6. [Fetching Dataset Instances (`fetch_instances.py`)](#-fetching-dataset-instances-fetch_instancespy)
7. [Generating Predictions with Minovative Mind CLI (`eval`)](#-generating-predictions-with-minovative-mind-cli-eval)
8. [Evaluation Harness (`run_eval.py` & `run_eval.sh`)](#-evaluation-harness-run_evalpy--run_evalsh)
9. [End-to-End Pipeline Script (`run_pipeline.sh`)](#-end-to-end-pipeline-script-run_pipelinesh)
10. [Validation & Helper CLI (`execute_benchmark.py`)](#-validation--helper-cli-execute_benchmarkpy)
11. [Apple Silicon & ARM64 Architecture Support](#-apple-silicon--arm64-architecture-support)
12. [Predictions File Schema](#-predictions-file-schema)
13. [Log Inspection & Evaluation Output](#-log-inspection--evaluation-output)
14. [Troubleshooting & Common Issues](#-troubleshooting--common-issues)

---

## 🔍 Overview

**SWE-bench** evaluates language models and coding agents on resolving real-world GitHub issues across popular Python repositories (such as `sympy`, `astropy`, `django`, `scikit-learn`, `pytest`, etc.).

### Key Benchmark Splits

- **SWE-bench Lite** (`SWE-bench/SWE-bench_Lite`): A curated subset of 300 task instances designed for faster evaluation, self-contained dependencies, and deterministic validation.
- **SWE-bench Verified** (`SWE-bench/SWE-bench_Verified`): A 500-instance subset human-validated for fairness, clear problem descriptions, and unit test accuracy.
- **SWE-bench Full** (`SWE-bench/SWE-bench`): The full 2,294-instance benchmark dataset.

---

## 💻 Prerequisites & System Requirements

- **Python**: Python 3.9 - 3.12 (Python 3.10+ recommended)
- **Docker**: Docker Desktop or Docker Engine running with permissions for current user.
- **Recommended Hardware**:
  - **CPUs**: 4 to 16 cores (evaluations run in parallel Docker containers)
  - **RAM**: Minimum 16 GB (32 GB recommended for concurrency > 4)
  - **Disk Space**: At least 50 GB to 120 GB of free space for Docker images, cache layers, and repository clones.

Verify your Docker daemon is active:

```bash
docker info
```

---

## ⚡ Quick Command Reference & Cheat Sheet

Run any evaluation workflow in 3 simple steps:

### 1. 🧪 Small Pilot Test (2 Instances)

```bash
# Step 1: Clean old predictions & fetch 2 test instances
rm -f predictions.jsonl evaluation_report.json
python fetch_instances.py --limit 2 --format jsonl --output test_instances.jsonl

# Step 2: Run Minovative Mind agent (generates predictions.jsonl & evaluation_report.json)
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i test_instances.jsonl -o predictions.jsonl -r evaluation_report.json --autoClone

# Step 3: Run Docker evaluation harness
./run_eval.sh -a -p predictions.jsonl -r pilot_eval -w 2

# View results:
cat minovative-mind-agent.pilot_eval.json
```

---

### 2. 🎯 Configurable Custom Tests

#### A. Run on a Specific Repository (e.g., 5 `sympy` issues)

```bash
# Fetch 5 sympy instances
python fetch_instances.py --repo sympy/sympy --limit 5 --format jsonl --output sympy_instances.jsonl

# Run agent
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i sympy_instances.jsonl -o predictions_sympy.jsonl -r report_sympy.json --autoClone

# Evaluate
./run_eval.sh -a -p predictions_sympy.jsonl -r eval_sympy -w 4
```

#### B. Run on a Specific Instance ID (e.g., `astropy__astropy-12907`)

```bash
# Run agent on single task
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i test_instances.jsonl --instanceId astropy__astropy-12907 -o predictions_single.jsonl -r report_single.json --autoClone

# Evaluate single task
./run_eval.sh -a -p predictions_single.jsonl -r eval_single -w 2
```

#### C. Run a Custom Batch (e.g., 10 or 20 random tasks)

```bash
# Fetch 10 tasks
python fetch_instances.py --limit 10 --format jsonl --output instances_10.jsonl

# Run agent with 2 parallel workers
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i instances_10.jsonl -o predictions_10.jsonl -r report_10.json --autoClone --concurrency 2

# Evaluate in Docker with 4 workers
./run_eval.sh -a -p predictions_10.jsonl -r eval_10 -w 4
```

---

---

### 3. 📦 Storage-Optimized Batch & Prune Strategy (Zero Bloat)

If you want to evaluate all 300 instances without consuming tens of gigabytes of disk space, evaluate repository-by-repository (or in batches of 25–50) and prune Docker images after each batch. **All your scorecards and logs are kept permanently on disk!**

```bash
# --- Batch 1: Astropy (6 instances) ---
python fetch_instances.py --repo astropy/astropy --format jsonl --output b1_astropy.jsonl
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i b1_astropy.jsonl -o preds_astropy.jsonl -r report_astropy.json --autoClone
./run_eval.sh -a -p preds_astropy.jsonl -r report_astropy -w 4
docker image prune -a  # Clean images (results are kept!)

# --- Batch 2: SymPy (50 instances) ---
python fetch_instances.py --repo sympy/sympy --format jsonl --output b2_sympy.jsonl
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i b2_sympy.jsonl -o preds_sympy.jsonl -r report_sympy.json --autoClone -c 2
./run_eval.sh -a -p preds_sympy.jsonl -r report_sympy -w 4
docker image prune -a  # Clean images (results are kept!)

# --- Batch 3: Django (115 instances) ---
python fetch_instances.py --repo django/django --format jsonl --output b3_django.jsonl
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i b3_django.jsonl -o preds_django.jsonl -r report_django.json --autoClone -c 2
./run_eval.sh -a -p preds_django.jsonl -r report_django -w 4
docker image prune -a  # Clean images (results are kept!)

# --- 🏆 Consolidate All Batch Reports into a Single Leaderboard Scorecard ---
python execute_benchmark.py report minovative-mind-agent.*.json -o full_benchmark_scorecard.json
```

---

### 4. 🏆 Full SWE-bench Lite Benchmark (All 300 in One Shot)

```bash
# Step 1: Fetch all 300 benchmark instances
python fetch_instances.py --format jsonl --output all_lite_instances.jsonl

# Step 2: Run agent across all 300 instances (with 2 concurrent workers)
node "/Users/danielward/Developer/Work Projects/minovative-mind-cli/bin/run.js" eval -i all_lite_instances.jsonl -o predictions_full.jsonl -r evaluation_report.json --autoClone --concurrency 2

# Step 3: Run full Docker evaluation harness (with 4 to 8 workers)
./run_eval.sh -a -p predictions_full.jsonl -r full_eval -w 4

# View official benchmark report:
cat minovative-mind-agent.full_eval.json
```

---

### 5. 🧹 Disk Space Cleanup (Anytime)

```bash
# Reclaim Docker image storage
docker image prune -a

# Reclaim cached git repositories
rm -rf ~/.cache/swe-bench-repos
```

---

## 🔄 Step-by-Step Execution Workflow

The end-to-end benchmarking and evaluation lifecycle consists of 4 discrete phases:

```
[1. Setup Environment] ➔ [2. Fetch Instances] ➔ [3. Generate Predictions] ➔ [4. Harness Evaluation]
     (setup_env.sh)     (fetch_instances.py)     (minovative-mind eval)       (run_eval.sh / Docker)
```

1. **Environment Setup**: Initialize Python 3.10+ virtualenv, install SWE-bench dependencies, and ensure Docker daemon is active.
2. **Fetch Instances**: Pull SWE-bench Lite benchmark instances and problem descriptions from Hugging Face into JSON or JSONL format.
3. **Agent Inference & Prediction**: Run Minovative Mind CLI (`minovative-mind-cli eval`) to autonomously solve issues across target repositories and export unified diff patches into `predictions.jsonl`.
4. **Harness Evaluation**: Execute the official SWE-bench evaluation harness inside isolated Docker containers to test patches against `FAIL_TO_PASS` and `PASS_TO_PASS` test suites.

---

## ⚙️ Quick Start & Environment Setup

### 1. Automated Environment Setup

Run the automated environment setup script to create a Python virtual environment (`venv/`) and install all required dependencies:

```bash
chmod +x setup_env.sh
./setup_env.sh
```

### 2. Manual Installation

If you prefer configuring the virtual environment manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

---

## 📥 Fetching Dataset Instances (`fetch_instances.py`)

The `fetch_instances.py` utility retrieves task metadata and issue descriptions from Hugging Face:

### Command Examples

```bash
# Activate the virtual environment
source venv/bin/activate

# Fetch the first 10 instances of SWE-bench Lite and print summary
python fetch_instances.py --limit 10

# Filter instances by repository (e.g., sympy)
python fetch_instances.py --repo sympy/sympy --limit 5

# Export instances to JSON
python fetch_instances.py --output instances_lite.json

# Export instances to JSONL format
python fetch_instances.py --format jsonl --output instances_lite.jsonl

# Fetch a specific dataset split (e.g. SWE-bench_Verified)
python fetch_instances.py --dataset SWE-bench/SWE-bench_Verified --limit 20
```

### Supported Arguments

| Argument    | Description                                         | Default                    |
| :---------- | :-------------------------------------------------- | :------------------------- |
| `--dataset` | Dataset repository name on Hugging Face             | `SWE-bench/SWE-bench_Lite` |
| `--split`   | Dataset split (`test`, `dev`, `train`)              | `test`                     |
| `--output`  | Destination output file path                        | `None` (stdout summary)    |
| `--format`  | Export format (`json` or `jsonl`)                   | `json`                     |
| `--limit`   | Maximum number of instances to retrieve             | All                        |
| `--repo`    | Filter by repository name (e.g., `astropy/astropy`) | All                        |

---

## 🤖 Generating Predictions with Minovative Mind CLI (`eval`)

The Minovative Mind CLI provides a built-in `eval` command runner powered by `SweBenchRunnerService` with automated Git workspace isolation and remote repository caching:

```bash
# Evaluate instances and output predictions.jsonl and evaluation_report.json
minovative-mind-cli eval --instances test_instances.jsonl --output predictions.jsonl --report evaluation_report.json --autoClone

# Run on a specific instance ID
minovative-mind-cli eval -i test_instances.jsonl -o predictions.jsonl -r report_single.json --instanceId astropy__astropy-12907 --autoClone

# Dry run mode to verify workspace resolution and prompts without making LLM calls
minovative-mind-cli eval -i test_instances.jsonl --dryRun

# Specify custom concurrency and max turns
minovative-mind-cli eval -i test_instances.jsonl -o predictions.jsonl -r evaluation_report.json -m minovative-mind-v1 --maxTurns 30 -c 2 --autoClone
```

### CLI Evaluation Options

| Flag                 | Description                                                                | Default             |
| :------------------- | :------------------------------------------------------------------------- | :------------------ |
| `-i, --instances`    | Path to input instances JSON or JSONL file                                 | _Required_          |
| `-o, --output`       | Path to destination `predictions.jsonl` output                             | `predictions.jsonl` |
| `-r, --report`       | Path to export comprehensive evaluation report JSON                        | `None` (Optional)   |
| `--autoClone`        | Automatically clone repository if not found locally in workspace directory | `false`             |
| `--instanceId`       | Filter by specific instance ID (e.g. `astropy__astropy-12907`)             | All instances       |
| `--repo`             | Filter instances by repository name (e.g. `astropy/astropy`)               | All repos           |
| `--limit`            | Limit the number of instances to evaluate                                  | All                 |
| `-w, --workspaceDir` | Base workspace directory where repo checkouts reside                       | Auto / CWD          |
| `--dryRun`           | Validate instances and workspace setup without invoking the agent loop     | `false`             |
| `-c, --concurrency`  | Number of instances to evaluate concurrently                               | `1`                 |
| `--maxTurns`         | Maximum agent execution turns per benchmark instance                       | `30`                |
| `--timeout`          | Timeout in milliseconds per instance                                       | `600000` (10m)      |
| `-v, --verbose`      | Show detailed per-turn logs during evaluation                              | `false`             |

---

## 🚀 Evaluation Harness (`run_eval.py` & `run_eval.sh`)

Evaluations execute isolated Docker test runners that:

1. Spin up the specific repository environment and Python version for the instance.
2. Apply your model's git patch (`model_patch`).
3. Run the repository's test suite to verify **FAIL_TO_PASS** (tests that failed before and must pass now) and **PASS_TO_PASS** (regression checks).

### Using the Bash Runner (`run_eval.sh`)

```bash
# Evaluate sample predictions
./run_eval.sh -p sample_predictions.jsonl

# Evaluate ground-truth gold reference patches (sanity check)
./run_eval.sh -g -i sympy__sympy-20590

# Run evaluation with custom concurrency and run identifier
./run_eval.sh -p my_model_predictions.jsonl -w 8 -r experiment_v1

# Run a specific subset of instances
./run_eval.sh -p my_model_predictions.jsonl -i "sympy__sympy-20590 astropy__astropy-12907"
```

### Using the Python Runner Directly (`run_eval.py`)

```bash
# Standard evaluation run
python run_eval.py \
  --dataset_name princeton-nlp/SWE-bench_Lite \
  --predictions_path sample_predictions.jsonl \
  --max_workers 4 \
  --run_id my_run_01

# Evaluate on SWE-bench Verified
python run_eval.py \
  --dataset_name princeton-nlp/SWE-bench_Verified \
  --predictions_path my_verified_predictions.jsonl \
  --max_workers 6

# Evaluate single instance with gold reference
python run_eval.py \
  --predictions_path gold \
  --instance_ids sympy__sympy-20590
```

### Key Evaluation Options

- `--dataset_name`: Name or path to the benchmark dataset.
- `--predictions_path`: Path to predictions `.jsonl` file, or `'gold'` for reference testing.
- `--max_workers`: Number of parallel Docker containers (defaults to 75% of available CPU cores).
- `--run_id`: Unique run tag used for log directories and output reports.
- `--instance_ids`: Filter one or more specific instance IDs.
- `--namespace`: Docker namespace (defaults to `''` for local builds on ARM64, and `'swebench'` on x86_64).
- `--force_local_build`: Force local container building.
- `--timeout`: Per-instance test suite timeout in seconds (default: 1800s).

---

## 🛠️ End-to-End Pipeline Script (`run_pipeline.sh`)

To execute the entire automated flow in one step:

```bash
chmod +x run_pipeline.sh
./run_pipeline.sh test_instances.jsonl
```

---

## 🔍 Validation & Helper CLI (`execute_benchmark.py`)

Validate predictions format and check patch stats before running the container harness:

```bash
# Validate format and print patch statistics
python execute_benchmark.py validate --predictions predictions.jsonl

# Run evaluation harness with validation
python execute_benchmark.py run --predictions predictions.jsonl --run_id my_run_01 --max_workers 4
```

---

## 🍏 Apple Silicon & ARM64 Architecture Support

Running SWE-bench on Apple Silicon (M1, M2, M3, M4) or Linux aarch64 architectures requires building Docker environment images locally rather than pulling prebuilt x86_64 images from DockerHub.

`run_eval.py` automatically detects Apple Silicon / ARM64 environments and configures:

1. `--namespace ''` (disables remote registry pulling to trigger local native image builds).
2. `DOCKER_BUILDKIT=1` build environment defaults.

If you ever need to manually force ARM64/local build mode:

```bash
./run_eval.sh -a -p sample_predictions.jsonl
# or
python run_eval.py --force_local_build --predictions_path sample_predictions.jsonl
```

---

## 📄 Predictions File Schema

Predictions must be formatted in a **JSONL** (JSON Lines) file where each line is a valid JSON object containing:

```json
{
	"instance_id": "sympy__sympy-20590",
	"model_name_or_path": "my-coding-agent-v1",
	"model_patch": "diff --git a/sympy/core/symbol.py b/sympy/core/symbol.py\n--- a/sympy/core/symbol.py\n+++ b/sympy/core/symbol.py\n@@ -200,6 +200,8 @@ def __new__(cls, name, **assumptions):\n+        if not isinstance(name, str):\n+            raise TypeError(\"name must be a string\")\n"
}
```

### Schema Requirements

- `instance_id` _(string, required)_: The target task instance identifier (e.g., `sympy__sympy-20590`).
- `model_name_or_path` _(string, optional)_: Identifier for the model/agent version generating the patch.
- `model_patch` _(string, required)_: Unified diff string (git diff) to be applied to the codebase.

See `sample_predictions.jsonl` for a reference template.

---

## 📊 Log Inspection & Evaluation Output

During and after evaluation, logs and metric reports are generated in the workspace:

```
├── logs/
│   ├── build_images/
│   │   └── <instance_id>.build.log       # Docker image build logs
│   └── run_evaluation/
│       └── <run_id>/
│           ├── <instance_id>.eval.log    # Test execution stdout/stderr
│           └── <instance_id>.patch       # Applied patch file
└── evaluation_results/
    └── <run_id>.json                     # Final aggregated benchmark scores
```

### Metric Definitions

- **Resolved**: The model patch passed all FAIL_TO_PASS tests while introducing 0 regressions on PASS_TO_PASS tests.
- **Unresolved**: The model patch either failed to fix the target issue or caused regression failures.
- **Error / Empty Patch**: The patch failed to apply via `git apply` or was empty.

---

## 🛠️ Troubleshooting & Common Issues

### 1. "Docker daemon is not running"

Ensure Docker Desktop is started and responsive:

```bash
docker ps
```

If you encounter permission errors on Linux:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 2. "No space left on device" (Docker disk limit)

SWE-bench builds Docker images for multiple repository environments. If disk space runs low:

```bash
# Remove dangling images and build cache
docker system prune -a --volumes
```

### 3. Architecture Mismatch / Emulation Hangs on macOS

Ensure you are using native local builds:

```bash
./run_eval.sh -a -p sample_predictions.jsonl
```

### 4. Patch Application Failures

Check `logs/run_evaluation/<run_id>/<instance_id>.eval.log`. Ensure your patches use standard unified git diff format with `a/` and `b/` relative file prefixes.

### 5. Easy to delete anytime

If you ever want to reclaim disk space, you can remove all cached benchmark repositories with:

```bash
rm -rf ~/.cache/swe-bench-repos
```
