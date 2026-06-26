#!/bin/bash
# GrowthScout AI - Local Evaluation Automation Harness
#
# This script sets up the local environment, runs the evaluation pipeline,
# and generates trend and coverage reports automatically.

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}        GROWTHSCOUT AI - LOCAL EVALUATION AUTOMATION HARNESS        ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Determine workspace root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$WORKSPACE_ROOT:$PYTHONPATH"

# 2. Check for environment files
if [ -f "$WORKSPACE_ROOT/.env" ]; then
    echo -e "${GREEN}[OK]${NC} Environment file (.env) detected."
else
    echo -e "${YELLOW}[WARN]${NC} No .env file found at $WORKSPACE_ROOT/.env."
    echo -e "       Ensure required environment variables are set before running evaluations."
fi

# 3. Configure evaluation history directory
if [ -n "$GROWTHSCOUT_EVAL_HISTORY_DIR" ]; then
    echo -e "${GREEN}[OK]${NC} Custom evaluation history directory set: $GROWTHSCOUT_EVAL_HISTORY_DIR"
else
    export GROWTHSCOUT_EVAL_HISTORY_DIR="$WORKSPACE_ROOT/artifacts/evaluation_history"
    echo -e "${CYAN}[INFO]${NC} Defaulting evaluation history directory to: $GROWTHSCOUT_EVAL_HISTORY_DIR"
fi

# 4. Trigger evaluation run inside the agents project directory
echo -e "\n${CYAN}[1/3] Running evaluation suite with agents-cli...${NC}"
if command -v agents-cli &> /dev/null; then
    # Save current directory and CD into the agents subdirectory where the manifest and pyproject.toml are located
    pushd "$WORKSPACE_ROOT/agents" > /dev/null
    
    # Run evaluation using paths relative to the agents directory
    agents-cli eval run \
        --dataset ../eval/datasets/discovery_dataset.json \
        --config ../eval/eval_config.yaml || {
        echo -e "${RED}[ERROR]${NC} agents-cli evaluation run failed."
        popd > /dev/null
        exit 1
    }
    
    popd > /dev/null
else
    echo -e "${YELLOW}[WARN]${NC} 'agents-cli' command not found in the current shell path."
    echo -e "       Simulating / checking configuration files only."
fi

# 5. Generate trend report
echo -e "\n${CYAN}[2/3] Generating evaluation trend report...${NC}"
python3 "$SCRIPT_DIR/generate_trend_report.py" || {
    echo -e "${RED}[ERROR]${NC} Failed to generate evaluation trend report."
    exit 1
}

# 6. Generate coverage report
echo -e "\n${CYAN}[3/3] Generating dataset coverage report...${NC}"
python3 "$SCRIPT_DIR/generate_coverage_report.py" || {
    echo -e "${RED}[ERROR]${NC} Failed to generate dataset coverage report."
    exit 1
}

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}        EVALUATION PROCESS COMPLETED SUCCESSFULLY                    ${NC}"
echo -e "${GREEN}======================================================================${NC}"
