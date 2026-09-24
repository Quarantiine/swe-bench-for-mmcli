#!/usr/bin/env bash
# Virtual environment setup script for SWE-bench MMCLI evaluation environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "========================================================"
echo " Setting up SWE-bench Environment in ${SCRIPT_DIR}"
echo "========================================================"

# Check Python availability and version
if ! command -v "${PYTHON_BIN}" &> /dev/null; then
    echo "Error: Python interpreter '${PYTHON_BIN}' not found in PATH." >&2
    exit 1
fi

PY_VERSION=$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python version: ${PY_VERSION} (using ${PYTHON_BIN})"

# Check Docker availability
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo "Docker daemon is running."
    else
        echo "Warning: Docker is installed but daemon is not running. Please start Docker before running evaluation."
    fi
else
    echo "Warning: Docker is not installed or not in PATH. Docker is required for SWE-bench evaluations."
fi

# Create virtual environment
if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment at ${VENV_DIR}..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
    echo "Existing virtual environment found at ${VENV_DIR}."
fi

# Activate virtual environment
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r "${SCRIPT_DIR}/requirements.txt"
else
    echo "Warning: requirements.txt not found in ${SCRIPT_DIR}."
fi

chmod +x "${SCRIPT_DIR}"/*.sh

echo "========================================================"
echo " Setup completed successfully!"
echo " Activate the environment with: source venv/bin/activate"
echo "========================================================"
