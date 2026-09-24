# ⚡ SWE-bench Lite with Minovative Mind CLI (`mmcli`)

An automated, turnkey benchmarking suite that connects the **Minovative Mind CLI (`mmcli`) autonomous coding agent** to **SWE-bench Lite**.

Evaluate AI coding agents on real-world GitHub issues, generate unified git diff patches, and validate them inside isolated Docker testbeds with full support for **Apple Silicon (M-series ARM64)** and **Linux/x86_64**.

---

> [!TIP]
> 🏆 **Verified Benchmark Result (`pilot_test`):** **5 out of 5 issues resolved (100.0% pass rate)** on `astropy/astropy` using **Gemini 3.7 Flash** at just **$3.18 total API cost** (~$0.64 per resolved issue) with an **84.8% prompt cache hit rate**. Read the full technical breakdown in [PILOT_TEST_REPORT.md](PILOT_TEST_REPORT.md).

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Step 1: Install & Set Up Minovative Mind Agent](#-step-1-install--set-up-minovative-mind-agent)
3. [Step 2: Set Up SWE-bench Environment](#-step-2-set-up-swe-bench-environment)
4. [Step 3: Run the Benchmark](#-step-3-run-the-benchmark)
5. [Step 4: View Scorecards & Diagnostics](#-step-4-view-scorecards--diagnostics)
6. [Command Cheat Sheet](#-command-cheat-sheet)
7. [Repository Structure](#-repository-structure)
8. [License](#-license)

---

## 💻 Prerequisites

Before running the evaluation, ensure you have:

- **Docker Desktop** installed and running (`docker info`)
- **Node.js** 18+ (for the `mmcli` agent)
- **Python** 3.10+
- A **Google AI Studio Gemini API Key**

---

## 🚀 Step 1: Install & Set Up Minovative Mind Agent

The evaluation pipeline uses the **Minovative Mind CLI (`mmcli`)** to autonomously investigate repositories, locate bugs, and generate code patches.

1. **Install the CLI globally:**

   ```bash
   npm install -g minovative-mind-cli@latest
   ```

2. **Authenticate with GitHub:**

   ```bash
   minovative-mind-cli login
   ```

3. **Configure your Google AI Studio API Key:**
   Launch the agent's interactive terminal:
   ```bash
   minovative-mind-cli chat
   ```
   Inside the chat prompt, run the slash command:
   ```text
   /config-key
   ```

   - Select **Set/Update API Key** and paste your Google AI Studio Gemini API key.
   - Enable **BYOK** (Bring Your Own Key) mode.

Your API key is securely encrypted on your local machine. Once configured, all SWE-bench evaluations will use this key automatically. Type `exit` to leave the chat.

---

## ⚙️ Step 2: Set Up SWE-bench Environment

Clone this repository and run the automated environment setup script:

```bash
git clone https://github.com/Quarantiine/swe-bench-for-mmcli.git
cd swe-bench-for-mmcli

# Initialize Python virtualenv and install dependencies:
./setup_env.sh
```

---

## 🎯 Step 3: Run the Benchmark

The [`run_pipeline.sh`](run_pipeline.sh) script handles the entire 5-stage lifecycle automatically (fetching instances, agent inference, Docker testing, and scorecard generation).

### 1. Quick 2-Instance Smoke Test

Verify everything is working end-to-end:

```bash
./run_pipeline.sh --limit 2
```

### 2. Run on a Specific Repository

Evaluate the agent on 5 issues from a specific library (e.g. Astropy or SymPy):

```bash
# Astropy (5 issues, 2 parallel Docker test workers)
./run_pipeline.sh --repo astropy/astropy --limit 5 --workers 2

# SymPy (5 issues, 4 parallel Docker test workers)
./run_pipeline.sh --repo sympy/sympy --limit 5 --workers 4
```

### 3. Run a Single Specific GitHub Issue

```bash
./run_pipeline.sh --instance-id sympy__sympy-20590
```

### 4. Run Full SWE-bench Lite (All 300 Instances)

```bash
./run_pipeline.sh --workers 4
```

---

## 📊 Step 4: View Scorecards & Diagnostics

After an evaluation completes, inspect the official resolution rates, token economics, and failure logs:

```bash
# View the scorecard for the latest run:
./post_eval.sh

# View a specific run report:
./post_eval.sh --report minovative-mind-agent.pilot_test.json

# Clean up Docker test images to reclaim disk space:
./post_eval.sh --clean-docker
```

---

## ⚡ Command Cheat Sheet

| Flag / Option             | Description                                             | Example                                       |
| :------------------------ | :------------------------------------------------------ | :-------------------------------------------- |
| `-l, --limit <NUM>`       | Limit the number of instances to evaluate               | `./run_pipeline.sh --limit 5`                 |
| `-r, --repo <REPO>`       | Filter by repository name                               | `./run_pipeline.sh --repo sympy/sympy`        |
| `-i, --instance-id <ID>`  | Run on a single specific task ID                        | `./run_pipeline.sh -i astropy__astropy-12907` |
| `-w, --workers <NUM>`     | Number of parallel Docker test runners (default: 2)     | `./run_pipeline.sh --workers 4`               |
| `-c, --concurrency <NUM>` | Number of agent instances solving issues in parallel    | `./run_pipeline.sh -c 2`                      |
| `--skip-agent`            | Skip agent generation and evaluate existing predictions | `./run_pipeline.sh --skip-agent`              |
| `--clean-docker`          | Automatically prune Docker test images after run        | `./run_pipeline.sh --clean-docker`            |
| `--force-fetch`           | Force re-downloading benchmark tasks from Hugging Face  | `./run_pipeline.sh --force-fetch`             |

---

## 📂 Repository Structure

```text
├── run_pipeline.sh         # 🚀 All-in-one automated evaluation pipeline
├── run_eval.sh             # 🐳 Convenience bash wrapper for Docker test harness
├── run_eval.py             # ⚙️ Core SWE-bench Docker container evaluation runner
├── post_eval.sh            # 📊 Convenience bash wrapper for post-eval scorecard
├── post_eval.py            # 🔍 Scorecard generator, failure diagnosis & log extractor
├── fetch_instances.py      # 📥 Hugging Face dataset downloader (Lite / Verified / Full)
├── setup_env.sh            # 🔧 Automated virtualenv & dependencies setup script
├── requirements.txt        # 📦 Python dependencies
├── PILOT_TEST_REPORT.md    # 🏆 Detailed technical report of the 5/5 pilot benchmark
└── README.md               # 📖 Documentation & quick start guide
```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
