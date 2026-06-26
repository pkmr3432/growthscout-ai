#!/usr/bin/env bash
# GrowthScout AI - Local & CI Evaluation Automation Harness
#
# This script sets up the local environment, runs the evaluation pipeline
# (supporting --pipeline fast vs --pipeline full), and generates reports.

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}        GROWTHSCOUT AI - EVALUATION AUTOMATION HARNESS              ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# Parse pipeline argument
PIPELINE="fast"
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --pipeline)
            if [ "$2" == "fast" ] || [ "$2" == "full" ]; then
                PIPELINE="$2"
            else
                echo -e "${RED}[ERROR]${NC} Invalid pipeline option: $2. Must be 'fast' or 'full'."
                exit 1
            fi
            shift
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unknown parameter passed: $1"
            echo -e "Usage: $0 [--pipeline fast|full]"
            exit 1
            ;;
    esac
    shift
done

echo -e "${CYAN}[INFO]${NC} Selected pipeline mode: ${YELLOW}${PIPELINE}${NC}"

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
mkdir -p "$GROWTHSCOUT_EVAL_HISTORY_DIR"

# Preflight Checks
echo -e "\n${CYAN}[PREFLIGHT] Running Preflight Manifest Validation...${NC}"
python3 "$SCRIPT_DIR/validate_manifest.py" || {
    echo -e "${RED}[ERROR]${NC} Preflight Manifest Validation failed."
    exit 1
}

echo -e "\n${CYAN}[PREFLIGHT] Running Dataset Integrity & Fingerprint Validation...${NC}"
python3 "$SCRIPT_DIR/dataset_integrity.py" --verify || {
    echo -e "${RED}[ERROR]${NC} Dataset Integrity Verification failed."
    exit 1
}

# 4. Handle dataset preparation based on pipeline mode
DATASET_PATH="$WORKSPACE_ROOT/eval/datasets/discovery_dataset.json"
IS_TEMP_DATASET=false

if [ "$PIPELINE" == "fast" ]; then
    # Load manifest to find subset count limit
    SUBSET_LIMIT=$(python3 -c "import yaml; print(yaml.safe_load(open('$WORKSPACE_ROOT/eval/quality_manifest.yaml'))['evaluation_cadence']['fast_ci']['max_cases_per_dataset'])" 2>/dev/null || echo 5)
    echo -e "${CYAN}[INFO]${NC} Fast pipeline enabled. Restricting evaluation to first $SUBSET_LIMIT cases."
    
    # Generate temporary subset dataset
    TEMP_DATASET_PATH="$WORKSPACE_ROOT/eval/datasets/discovery_dataset_fast_subset.json"
    python3 -c "
import json
with open('$DATASET_PATH') as f:
    d = json.load(f)
d['eval_cases'] = d['eval_cases'][:$SUBSET_LIMIT]
with open('$TEMP_DATASET_PATH', 'w') as f:
    json.dump(d, f, indent=2)
"
    DATASET_PATH="$TEMP_DATASET_PATH"
    IS_TEMP_DATASET=true
fi

# 5. Trigger evaluation run inside the agents project directory
echo -e "\n${CYAN}[1/4] Running evaluation suite with agents-cli...${NC}"
if [ "$GROWTHSCOUT_MOCK_EVAL" == "true" ]; then
    echo -e "${YELLOW}[MOCK]${NC} Simulating evaluation run. Copying mock candidate results..."
    mkdir -p "$WORKSPACE_ROOT/artifacts/grade_results"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    cp "$WORKSPACE_ROOT/eval/baselines/mock_candidate_results.json" "$WORKSPACE_ROOT/artifacts/grade_results/results_${TIMESTAMP}.json"
    echo -e "${GREEN}[OK]${NC} Mock results written to artifacts/grade_results/results_${TIMESTAMP}.json"
elif command -v agents-cli &> /dev/null; then
    pushd "$WORKSPACE_ROOT/agents" > /dev/null
    
    agents-cli eval run \
        --dataset "$DATASET_PATH" \
        --config ../eval/eval_config.yaml || {
        echo -e "${RED}[ERROR]${NC} agents-cli evaluation run failed."
        # Clean up if needed
        if [ "$IS_TEMP_DATASET" = true ]; then rm -f "$DATASET_PATH"; fi
        popd > /dev/null
        exit 1
    }
    
    popd > /dev/null
else
    echo -e "${YELLOW}[WARN]${NC} 'agents-cli' command not found in the current shell path."
    echo -e "       Simulating / checking configuration files only."
fi

# Clean up temp dataset if generated
if [ "$IS_TEMP_DATASET" = true ]; then
    rm -f "$DATASET_PATH"
fi

# 6. Generate trend and coverage reports for full runs
if [ "$PIPELINE" == "full" ]; then
    echo -e "\n${CYAN}[2/4] Generating evaluation trend report...${NC}"
    python3 "$SCRIPT_DIR/generate_trend_report.py" || {
        echo -e "${RED}[ERROR]${NC} Failed to generate evaluation trend report."
        exit 1
    }
    
    echo -e "\n${CYAN}[3/4] Generating dataset coverage report...${NC}"
    python3 "$SCRIPT_DIR/generate_coverage_report.py" || {
        echo -e "${RED}[ERROR]${NC} Failed to generate dataset coverage report."
        exit 1
    }
else
    echo -e "\n${CYAN}[2/4] Skipping trend and coverage reports in Fast CI mode.${NC}"
    echo -e "${CYAN}[3/4] Skipping dataset coverage report in Fast CI mode.${NC}"
fi

# 7. Quality Gate Enforcement
PIPELINE_ARG="fast_ci"
if [ "$PIPELINE" == "full" ]; then
    PIPELINE_ARG="full_eval"
fi

echo -e "\n${CYAN}[4/4] Executing CI/CD Quality Gate & Regression Check...${NC}"
python3 "$SCRIPT_DIR/compare_ci_regression.py" --pipeline "$PIPELINE_ARG" || {
    echo -e "${RED}[ERROR]${NC} CI/CD Quality Gate Check failed."
    # Trigger Diagnostics and Recommendations on failure
    echo -e "${YELLOW}[INFO]${NC} Triggering Regression Diagnostics..."
    python3 "$SCRIPT_DIR/regression_diagnostics.py"
    echo -e "${YELLOW}[INFO]${NC} Generating Structured Recommendations..."
    python3 "$SCRIPT_DIR/recommendation_engine.py"
    
    # Run report generator even on failure to capture failure results
    python3 "$SCRIPT_DIR/generate_ci_report.py" --pipeline "$PIPELINE_ARG"
    exit 1
}

# 8. Compile Trend Analytics and Recommendations on success
echo -e "\n${CYAN}[SUCCESS] Compiling Long-term Trends & Actionable Recommendations...${NC}"
python3 "$SCRIPT_DIR/trend_intelligence.py"
python3 "$SCRIPT_DIR/recommendation_engine.py"

# 9. Report Generator
python3 "$SCRIPT_DIR/generate_ci_report.py" --pipeline "$PIPELINE_ARG" || {
    echo -e "${RED}[ERROR]${NC} CI Report generation failed."
    exit 1
}

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}        EVALUATION PROCESS COMPLETED SUCCESSFULLY                    ${NC}"
echo -e "${GREEN}======================================================================${NC}"
