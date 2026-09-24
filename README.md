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
10. [Post-Benchmark Analysis & Cleanup Runner (`post_eval.py` & `post_eval.sh`)](#-post-benchmark-analysis--cleanup-runner-post_evalpy--post_evalsh)
11. [Validation & Helper CLI (`execute_benchmark.py`)](#-validation--helper-cli-execute_benchmarkpy)
12. [Apple Silicon & ARM64 Architecture Support](#-apple-silicon--arm64-architecture-support)
13. [Predictions File Schema](#-predictions-file-schema)
14. [Log Inspection & Evaluation Output](#-log-inspection--evaluation-output)
15. [Troubleshooting & Common Issues](#-troubleshooting--common-issues)

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

### 0. 🚀 Automated All-in-One Pipeline (`run_pipeline.sh`)

Run the complete 5-stage evaluation lifecycle with a single command (auto-detects/sets up venv, fetches instances, generates agent predictions, runs Docker evaluation, and generates post-eval scorecard with failure diagnosis):

```bash
# Ensure scripts are executable (one-time setup)
chmod +x *.sh

# Run a quick 2-instance pilot test
./run_pipeline.sh --limit 2

# Filter by repository with custom worker count
./run_pipeline.sh --repo sympy/sympy --limit 5 --workers 4

# Test a single issue end-to-end
./run_pipeline.sh --instance-id sympy__sympy-20590

# Benchmark SWE-bench Verified with custom turn limits
./run_pipeline.sh --dataset SWE-bench/SWE-bench_Verified --limit 10 --max-turns 40 --workers 4

# Run evaluation, export unresolved tasks to JSONL, and prune Docker images automatically
./run_pipeline.sh --limit 5 -j failed_tasks.jsonl --clean-docker
```

---

### 0.1. 📊 Post-Benchmark Analysis & Cleanup (`post_eval.sh` / `post_eval.py`)

Analyze results, diagnose failures, export unresolved tasks for re-runs, and clean Docker/cache:

```bash
# Generate scorecard and failure analysis from latest run
./post_eval.sh

# Analyze specific run and export unresolved instance IDs for targeted re-runs
./post_eval.sh --run-id pilot_eval -u unresolved_tasks.txt

# Filter source JSONL dataset to only failing instances for instant re-running
./post_eval.sh --export-jsonl failed_instances.jsonl --instances-source test_instances.jsonl

# Generate post-eval summary scorecard and clean up Docker resources & cache
./post_eval.sh --clean-all
```

---

### 1. 🧪 Manual Pilot Test (2 Instances)

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

The end-to-end benchmarking and evaluation lifecycle consists of 5 discrete phases:

```
[1. Setup Environment] ➔ [2. Fetch Instances] ➔ [3. Generate Predictions] ➔ [4. Harness Evaluation] ➔ [5. Post-Eval & Cleanup]
     (setup_env.sh)     (fetch_instances.py)     (minovative-mind eval)       (run_eval.sh / Docker)     (post_eval.sh / post_eval.py)
```

1. **Environment Setup**: Initialize Python 3.10+ virtualenv, install SWE-bench dependencies, and ensure Docker daemon is active.
2. **Fetch Instances**: Pull SWE-bench Lite benchmark instances and problem descriptions from Hugging Face into JSON or JSONL format.
3. **Agent Inference & Prediction**: Run Minovative Mind CLI (`minovative-mind-cli eval`) to autonomously solve issues across target repositories and export unified diff patches into `predictions.jsonl`.
4. **Harness Evaluation**: Execute the official SWE-bench evaluation harness inside isolated Docker containers to test patches against `FAIL_TO_PASS` and `PASS_TO_PASS` test suites.
5. **Post-Benchmark Analysis & Cleanup**: Consolidate benchmark scorecards and agent token economics, extract diagnostic failure log tracebacks, export unresolved tasks for iterative re-runs, and clean up Docker resources and repository caches.

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

## 🛠️ End-to-End Automated Pipeline Script (`run_pipeline.sh`)

`run_pipeline.sh` is an all-in-one automation orchestrator designed to execute the complete SWE-bench benchmarking lifecycle from a single command.

### 🌟 Automated 5-Stage Lifecycle

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       run_pipeline.sh Execution Flow                                  │
├───────────────────┬────────────────────┬───────────────────────┬─────────────────────┬────────────────┤
│ (1) Environment   │ (2) Instance Fetch │ (3) Agent Predictions │ (4) Docker Harness  │ (5) Post-Eval  │
│   • Detects venv  │   • Hugging Face   │   • Minovative Mind   │   • Docker testbed  │   • Scorecard  │
│   • Auto-creates  │   • Applies limits │     CLI agent         │   • Applies patches │   • Diagnostics│
│   • Installs deps │   • Repo/ID filter │   • Generates patches │   • PASS/FAIL tests │   • Failures   │
│   • Checks Docker │   • JSONL export   │   • Workspace isol.   │   • Generates score │   • Prune/Clean│
└───────────────────┴────────────────────┴───────────────────────┴─────────────────────┴────────────────┘
```

1. **Virtual Environment Auto-Verification**: Checks for `venv/` or `.venv/`, automatically initializes the environment using `python3 -m venv venv`, upgrades core tools (`pip`, `setuptools`, `wheel`), and installs `requirements.txt` if missing.
2. **Benchmark Instance Retrieval**: Invokes `fetch_instances.py` with your specified dataset split, repository filter, instance ID, and limit. Automatically caches instances or skips if already fetched.
3. **Agent Inference & Prediction Generation**: Invokes the Minovative Mind CLI (`eval` command) to autonomously investigate each issue, clone repositories, and export unified diff patches into `predictions.jsonl` along with detailed reports.
4. **Official Docker Test Harness Evaluation**: Validates Docker daemon status, applies platform architecture settings (automatic Apple Silicon / ARM64 support), runs test suites in parallel containers, and generates final evaluation scorecards.
5. **Post-Benchmark Analysis & Resource Cleanup**: Automatically runs `post_eval.py` to display unified resolution rates, per-repository breakdowns, prompt cache hit rates, failure excerpts, exports unresolved instances, and optionally prunes Docker test containers and images.

---

### 📖 CLI Options & Parameter Reference

| Flag / Option                          | Long Flag                    | Description                                                                                                         | Default                    |
| :------------------------------------- | :--------------------------- | :------------------------------------------------------------------------------------------------------------------ | :------------------------- |
| **Filtering & Limits**                 |                              |                                                                                                                     |                            |
| `-l`                                   | `--limit <NUM>`              | Maximum number of benchmark instances to evaluate (e.g. `2`, `5`, `10`)                                             | All instances              |
| `-r`                                   | `--repo <REPO>`              | Filter instances by repository name (e.g. `sympy/sympy`, `django/django`, `astropy/astropy`)                        | All repos                  |
| `-i`                                   | `--instance-id <ID>`         | Filter by specific instance ID (e.g. `sympy__sympy-20590`)                                                          | None                       |
| `-d`                                   | `--dataset <NAME>`           | Hugging Face dataset identifier (`SWE-bench/SWE-bench_Lite`, `SWE-bench/SWE-bench_Verified`, `SWE-bench/SWE-bench`) | `SWE-bench/SWE-bench_Lite` |
| `-s`                                   | `--split <SPLIT>`            | Dataset split to evaluate (`test`, `dev`, `train`)                                                                  | `test`                     |
| **Performance & Execution**            |                              |                                                                                                                     |                            |
| `-w`                                   | `--workers <NUM>`            | Maximum parallel Docker evaluation workers                                                                          | `2`                        |
| `-m`                                   | `--max-turns <NUM>`          | Maximum agent execution turns per benchmark instance                                                                | `30`                       |
| `-t`                                   | `--timeout <SEC>`            | Timeout per instance test run in seconds                                                                            | `1800` (30m)               |
| `-c`                                   | `--concurrency <NUM>`        | Number of benchmark instances for the agent to evaluate concurrently                                                | `1`                        |
| `-a`                                   | `--arm64`                    | Force ARM64 / Apple Silicon local container build settings                                                          | Auto-detected              |
| **File Paths & Metadata**              |                              |                                                                                                                     |                            |
| `-f`                                   | `--instances <PATH>`         | Path to instances JSONL file                                                                                        | `test_instances.jsonl`     |
| `-p`                                   | `--predictions <PATH>`       | Destination path for output `predictions.jsonl` file                                                                | `predictions.jsonl`        |
|                                        | `--report <PATH>`            | Path to export agent execution report JSON                                                                          | `evaluation_report.json`   |
|                                        | `--run-id <ID>`              | Custom run identifier for logs and scorecard files                                                                  | Auto-generated timestamp   |
|                                        | `--model <NAME>`             | Model identifier tag for prediction metadata                                                                        | `minovative-mind-agent`    |
|                                        | `--cache <LEVEL>`            | Docker harness cache level (`none`, `base`, `env`, `instance`)                                                      | `env`                      |
| **Pipeline Stage Controls**            |                              |                                                                                                                     |                            |
|                                        | `--skip-fetch`               | Skip instance fetching stage (re-use existing instances file)                                                       | `false`                    |
|                                        | `--skip-agent`               | Skip agent prediction generation (evaluate existing predictions file)                                               | `false`                    |
|                                        | `--skip-eval`                | Skip Docker evaluation harness stage (only fetch & generate patches)                                                | `false`                    |
|                                        | `--skip-post-eval`           | Skip post-benchmark scorecard analysis & cleanup step                                                               | `false`                    |
|                                        | `--post-eval`                | Explicitly enable post-evaluation analysis stage                                                                    | `true`                     |
|                                        | `--force-fetch`              | Force re-fetching instances from Hugging Face even if file exists                                                   | `false`                    |
|                                        | `--dry-run`                  | Dry run mode for agent predictions (validates setup without LLM calls)                                              | `false`                    |
|                                        | `--no-auto-clone`            | Disable automatic Git repository cloning during agent run                                                           | `false`                    |
| `-g`                                   | `--gold`                     | Evaluate ground-truth gold reference patches directly (sanity check)                                                | `false`                    |
| `-v`                                   | `--verbose`                  | Enable verbose debug logging throughout execution                                                                   | `false`                    |
| **Post-Eval Hooks & Resource Cleanup** |                              |                                                                                                                     |                            |
| `-u`                                   | `--export-unresolved <PATH>` | Export unresolved/failed instance IDs to text file (one ID per line)                                                | None                       |
| `-j`                                   | `--export-jsonl <PATH>`      | Export unresolved instances as filtered JSONL for immediate re-runs                                                 | None                       |
|                                        | `--post-eval-report <PATH>`  | Save consolidated post-eval scorecard to JSON file                                                                  | None                       |
|                                        | `--max-failures <NUM>`       | Maximum number of failure logs to display in terminal                                                               | `5`                        |
|                                        | `--no-logs`                  | Skip failure log extraction in post-eval summary                                                                    | `false`                    |
|                                        | `--clean-docker`             | Remove stopped test containers & SWE-bench Docker images after eval                                                 | `false`                    |
|                                        | `--clean-cache`              | Clear SWE-bench git repository cache (`~/.cache/swe-bench-repos`)                                                   | `false`                    |
|                                        | `--clean-all, --prune`       | Complete cleanup of Docker images, containers & git repo cache                                                      | `false`                    |
| `-h`                                   | `--help`                     | Display CLI help menu and option summary                                                                            | —                          |
| `-v`                                   | `--verbose`                  | Enable verbose debug logging throughout execution                                                                   | `false`                    |
| `-h`                                   | `--help`                     | Display CLI help menu and option summary                                                                            | —                          |

---

### 💡 Comprehensive Pipeline Usage Examples

#### 1. Quick Pilot Run with Configurable Limits

Run a rapid smoke test with 2 or 5 instances to verify end-to-end functionality:

```bash
# Evaluate 2 instances end-to-end
./run_pipeline.sh --limit 2

# Evaluate 5 instances with custom model tag and 4 Docker workers
./run_pipeline.sh --limit 5 --workers 4 --model my-custom-agent
```

#### 2. Filter by Repository with Limits

Target specific repositories (e.g. `sympy`, `django`, `pytest`, `astropy`) with constrained limits:

```bash
# Run 5 SymPy issues with 4 parallel Docker test workers
./run_pipeline.sh --repo sympy/sympy --limit 5 --workers 4

# Run 10 Django issues with max 40 agent turns per instance
./run_pipeline.sh --repo django/django --limit 10 --max-turns 40 --workers 4

# Run 3 Astropy issues
./run_pipeline.sh --repo astropy/astropy --limit 3
```

#### 3. Single Instance End-to-End Debugging

Pinpoint a single benchmark instance from fetch to agent fix and Docker validation:

```bash
./run_pipeline.sh --instance-id sympy__sympy-20590
```

#### 4. Evaluating SWE-bench Verified or Full

Switch datasets easily while controlling limits and timeouts:

```bash
# Run on 10 instances of SWE-bench Verified
./run_pipeline.sh --dataset SWE-bench/SWE-bench_Verified --limit 10 --max-turns 40 --workers 4

# Run on SWE-bench Full dev split
./run_pipeline.sh --dataset SWE-bench/SWE-bench --split dev --limit 5
```

#### 5. Selective Pipeline Stages (Skipping & Fast Iteration)

Mix and match stages to save time during agent development:

```bash
# Case A: Only fetch instances and generate agent predictions (skip Docker evaluation)
./run_pipeline.sh --limit 5 --skip-eval

# Case B: Re-evaluate an existing predictions.jsonl file without re-running the agent
./run_pipeline.sh -p predictions.jsonl --skip-fetch --skip-agent --workers 4

# Case C: Dry-run test of agent harness without calling LLMs
./run_pipeline.sh --limit 3 --dry-run
```

#### 6. Sanity Checking with Ground-Truth Gold Patches

Evaluate reference dataset patches directly to verify test harness correctness:

```bash
./run_pipeline.sh --gold --repo sympy/sympy --limit 3 --workers 2
```

#### 7. High-Throughput Parallel Evaluation

Leverage agent concurrency and multiple Docker workers for fast large-scale runs:

```bash
./run_pipeline.sh --limit 25 --concurrency 2 --workers 8 --timeout 1200
```

#### 8. Integrated Post-Evaluation & Storage Pruning

Run the end-to-end evaluation pipeline with automatic post-evaluation failure export and Docker container/image cleanup:

```bash
# Run 5 instances, export unresolved tasks to JSONL, and clean Docker images
./run_pipeline.sh --limit 5 --export-jsonl failed_tasks.jsonl --clean-docker

# Run full evaluation, export scorecard JSON, and perform full cleanup of Docker and cache
./run_pipeline.sh --limit 10 --post-eval-report summary.json --clean-all
```

---

## 📈 Post-Benchmark Analysis & Cleanup Runner (`post_eval.py` & `post_eval.sh`)

Once evaluations complete, the **Post-Benchmark Analysis & Cleanup Runner** (`post_eval.py` and `./post_eval.sh`) consolidates benchmark scorecards, diagnoses test failures, exports unresolved instances for iterative re-runs, and safely manages Docker and repository disk storage.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Post-Benchmark Analysis Lifecycle                         │
├───────────────────┬────────────────────┬───────────────────────┬───────────────────────┤
│ (1) Consolidate   │ (2) Diagnose       │ (3) Export for Re-run │ (4) Reclaim Storage   │
│   • Parse harness │   • Extract failed │   • Export TXT list   │   • Prune containers  │
│     JSON results  │     test names     │   • Filtered JSONL    │   • Remove SWE images │
│   • Combine token │   • Parse F2P/P2P  │   • Ready-to-run CLI  │   • Clear repo cache  │
│     economics     │   • High-signal log│     re-run commands   │     (~/.cache/repos)  │
└───────────────────┴────────────────────┴───────────────────────┴───────────────────────┘
```

### 🌟 Key Capabilities

1. **Unified Leaderboard Scorecard**: Merges harness test results (`resolved`, `unresolved`, `error`, `empty_patch`) with agent generation economics (prompt cache hit rate, token usage, average latency, diff size, and circuit breaker trip counts).
2. **Per-Repository Pass Rates**: Generates structured repository-by-repository resolution breakdowns with color-coded success rates.
3. **Deep Failure Diagnostics**: Automatically parses `logs/run_evaluation/<run_id>/<instance_id>/report.json`, `test_output.txt`, and `run_instance.log` to extract the exact failing test names and root-cause stack traces without manual grepping.
4. **Targeted Re-runs & Iteration**: Exports unresolved instances to a plain text file (one ID per line) or a filtered JSONL dataset (`test_instances.jsonl`), printing ready-to-run `run_pipeline.sh` commands for instant re-testing.
5. **Zero-Bloat Disk Cleanup**: Reclaims tens of gigabytes of disk space by pruning stopped evaluation containers, removing SWE-bench Docker images, clearing builder cache, and purging git repository clone caches (`~/.cache/swe-bench-repos`).

---

### 📖 CLI Options Reference (`post_eval.sh` & `post_eval.py`)

Both `./post_eval.sh` (convenience bash wrapper) and `python post_eval.py` support the full set of diagnostic and cleanup options:

| Flag / Option                    | Long Flag                    | Description                                                                  | Default                    |
| :------------------------------- | :--------------------------- | :--------------------------------------------------------------------------- | :------------------------- |
| **Reports & Run Identification** |                              |                                                                              |                            |
| `-r`                             | `--run-id <ID>`              | Evaluation run identifier to locate results and logs                         | Auto-detected              |
| `-e`                             | `--report <PATH...>`         | Path(s) or glob pattern to evaluation JSON result files (e.g. `*.eval.json`) | Auto-detected              |
|                                  | `--agent-report <PATH>`      | Path to agent prediction generation report JSON                              | `evaluation_report.json`   |
| **Diagnostics & Log Filtering**  |                              |                                                                              |                            |
|                                  | `--max-failures <NUM>`       | Maximum number of failure log excerpts to display in terminal                | `5`                        |
|                                  | `--no-logs`                  | Skip searching and extracting diagnostic test failure log snippets           | `false`                    |
| **Export & Targeted Re-runs**    |                              |                                                                              |                            |
| `-u`                             | `--export-unresolved <PATH>` | Export unresolved/failed instance IDs to a text file (one ID per line)       | None                       |
| `-j`                             | `--export-jsonl <PATH>`      | Export unresolved instances as a filtered JSONL dataset for re-running       | None                       |
| `-s`                             | `--instances-source <PATH>`  | Source instances JSONL file to filter for `--export-jsonl`                   | `test_instances.jsonl`     |
| `-o`                             | `--output-summary <PATH>`    | Save consolidated post-eval scorecard to JSON file                           | None                       |
|                                  | `--json`                     | Output raw consolidated scorecard JSON to stdout                             | `false`                    |
| **Disk Storage & Cache Cleanup** |                              |                                                                              |                            |
|                                  | `--clean-docker`             | Remove stopped test containers and local SWE-bench Docker images             | `false`                    |
|                                  | `--clean-docker-containers`  | Remove only stopped SWE-bench evaluation containers                          | `false`                    |
|                                  | `--clean-docker-images`      | Remove only SWE-bench Docker container images and build layers               | `false`                    |
|                                  | `--clean-cache`              | Clear SWE-bench git repository cache (`~/.cache/swe-bench-repos`)            | `false`                    |
|                                  | `--cache-dir <PATH>`         | Custom repository cache directory path                                       | `~/.cache/swe-bench-repos` |
|                                  | `--clean-all, --prune`       | Complete cleanup (containers, images, builder cache, and repo cache)         | `false`                    |
|                                  | `--dry-run`                  | Simulate cleanup operations without deleting any files or containers         | `false`                    |
| `-h`                             | `--help`                     | Display CLI help menu and option summary                                     | —                          |

---

### 📊 Scorecard Output Sample

When executed, `post_eval` renders a terminal scorecard:

```text
===========================================================================
  🏆 SWE-BENCH POST-BENCHMARK EVALUATION SCORECARD
===========================================================================
  Run Identifier:                eval_20260825_141952
  Report Source(s):              minovative-mind-agent.eval_20260825_141952.json
  Total Tasks Evaluated:         5
  Successfully Resolved:         4 (80.0%)
  Unresolved Instances:          1
---------------------------------------------------------------------------
  📊 REPOSITORY RESOLUTION BREAKDOWN
  Repository                     Resolved   Total      Resolution Rate
  -----------------------------------------------------------------
  astropy/astropy                4          5           80.0%
---------------------------------------------------------------------------
  🤖 AGENT GENERATION & TOKEN ECONOMICS
  Generation Patch Rate:         5/5 (100%)
  Average Agent Latency:         372.6s / instance
  Average Patch Size:            9878 chars
  Total Tokens Consumed:         30,835,315
  Prompt Cache Hit Rate:         45.5% (14,018,332 cached tokens)
  Circuit Breaker Trips:         21 trips, 6,297 lines pruned
===========================================================================

===========================================================================
  🔍 FAILURE DIAGNOSTICS & TEST LOG EXCERPTS (1 Failing Task)
===========================================================================

  Instance: astropy__astropy-14182
  Failure Category: FAIL_TO_PASS_FAILED
  Failed Tests: [F2P] astropy/io/ascii/tests/test_rst.py::test_rst_header_rows
  Log File: logs/run_evaluation/eval_20260825_141952/astropy__astropy-14182/run_instance.log
  Diagnostic Log Snippet:
  ----------------------------------------------------------------------
    FAILED astropy/io/ascii/tests/test_rst.py::test_rst_header_rows
    AssertionError: assert '===' in header_lines[0]
  ----------------------------------------------------------------------

===========================================================================
  🔁 TARGETED RE-RUN INSTRUCTIONS
===========================================================================
  Run directly with run_pipeline.sh:
    ./run_pipeline.sh --instance-id astropy__astropy-14182
===========================================================================
```

---

### 💡 Workflow Examples & Common Recipes

#### 1. Instant Post-Run Scorecard & Diagnostics

Analyze the most recent benchmark run in the workspace:

```bash
./post_eval.sh
```

#### 2. Analyze Specific Run by ID

Inspect logs and test results for a specific evaluation tag:

```bash
./post_eval.sh --run-id pilot_eval
```

#### 3. Export Unresolved Tasks to JSONL & Iterate

Quickly extract only the instances that failed, and immediately pass them into another pipeline run:

```bash
# Step 1: Export failing instances to filtered JSONL
./post_eval.sh --export-jsonl failed_tasks.jsonl --instances-source test_instances.jsonl

# Step 2: Re-run agent and test harness exclusively on failed tasks
./run_pipeline.sh --instances failed_tasks.jsonl --max-turns 40 --workers 2
```

#### 4. Export Failed Task IDs to Plain Text

Generate a simple text list of failed IDs for scripting or batch processing:

```bash
./post_eval.sh -u failed_instance_ids.txt

# Re-run directly:
./run_pipeline.sh --instance-id $(cat failed_instance_ids.txt | tr "\n" " ")
```

#### 5. Post-Benchmark Storage Recovery (Zero Bloat)

Clean up Docker images, stopped test containers, and git repository caches after completing evaluations:

```bash
# Dry run to preview what would be deleted
./post_eval.sh --clean-all --dry-run

# Reclaim all container and cache disk space
./post_eval.sh --clean-all
```

#### 6. Export Structured JSON Scorecard for CI/CD Integration

```bash
# Save JSON scorecard summary to file
./post_eval.sh -o evaluation_summary.json

# Or stream JSON directly to stdout
./post_eval.sh --json | jq '.resolution_rate_percent'
```

#### 7. Using Python Directly (`post_eval.py`)

```bash
python post_eval.py --report evaluation_results/*.json --agent-report evaluation_report.json -u unresolved.txt
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
│           ├── <instance_id>/
│           │   ├── report.json           # Individual test resolution status
│           │   ├── test_output.txt       # Pytest / test execution output
│           │   ├── run_instance.log      # Complete container execution log
│           │   └── patch.diff            # Applied patch
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
