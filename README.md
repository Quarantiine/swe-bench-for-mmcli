# SWE-bench Evaluation Harness & Benchmark Suite

An automated evaluation framework and benchmarking suite for **SWE-bench** (Lite, Full, and Verified), specifically optimized for automated coding agents, continuous benchmarking, and local reproduction with cross-platform support including **Apple Silicon (M-series ARM64)** and Linux/x86_64.

---

## 📋 Table of Contents

1. [Overview](#-overview)
2. [Prerequisites & System Requirements](#-prerequisites--system-requirements)
3. [Quick Start & Environment Setup](#-quick-start--environment-setup)
4. [Fetching Dataset Instances (`fetch_instances.py`)](#-fetching-dataset-instances-fetch_instancespy)
5. [Evaluation Harness (`run_eval.py` & `run_eval.sh`)](#-evaluation-harness-run_evalpy--run_evalsh)
6. [Apple Silicon & ARM64 Architecture Support](#-apple-silicon--arm64-architecture-support)
7. [Predictions File Schema](#-predictions-file-schema)
8. [Log Inspection & Evaluation Output](#-log-inspection--evaluation-output)
9. [Troubleshooting & Common Issues](#-troubleshooting--common-issues)

---

## 🔍 Overview

**SWE-bench** evaluates language models and coding agents on resolving real-world GitHub issues across popular Python repositories (such as `sympy`, `astropy`, `django`, `scikit-learn`, `pytest`, etc.).

### Key Benchmark Splits

- **SWE-bench Lite** (`princeton-nlp/SWE-bench_Lite`): A curated subset of 300 task instances designed for faster evaluation, self-contained dependencies, and deterministic validation.
- **SWE-bench Verified** (`princeton-nlp/SWE-bench_Verified`): A 500-instance subset human-validated for fairness, clear problem descriptions, and unit test accuracy.
- **SWE-bench Full** (`princeton-nlp/SWE-bench`): The full 2,294-instance benchmark dataset.

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
python fetch_instances.py --dataset princeton-nlp/SWE-bench_Verified --limit 20
```

### Supported Arguments

| Argument    | Description                                         | Default                        |
| :---------- | :-------------------------------------------------- | :----------------------------- |
| `--dataset` | Dataset repository name on Hugging Face             | `princeton-nlp/SWE-bench_Lite` |
| `--split`   | Dataset split (`test`, `dev`, `train`)              | `test`                         |
| `--output`  | Destination output file path                        | `None` (stdout summary)        |
| `--format`  | Export format (`json` or `jsonl`)                   | `json`                         |
| `--limit`   | Maximum number of instances to retrieve             | All                            |
| `--repo`    | Filter by repository name (e.g., `astropy/astropy`) | All                            |

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
