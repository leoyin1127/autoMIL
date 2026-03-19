#!/bin/bash
# SLURM test job: run feature extraction pipeline with 1 encoder
#
# Tests the full pipeline end-to-end (segmentation → patching → extraction)
# on 3 slides with conch_v15 (smallest at 768-dim) to fail fast if anything is broken.
#
# Usage:
#   sbatch benchmarks/scripts/submit_test_extraction.sh

#SBATCH --job-name=clwd_extract_test
#SBATCH --account=def-wanglab
#SBATCH --time=0-00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=12
#SBATCH --gpus=h100:1
#SBATCH --mem=64G
#SBATCH --output=logs/extract_test_%j.out
#SBATCH --error=logs/extract_test_%j.err

# ==================== CONFIG ====================
DATASET="clwd"
TEST_ENCODER="virchow2"
PROJECT_DIR="/home/yinshuol/scratch/autoMIL/autoMIL"

echo "================================================"
echo "AutoBench Feature Extraction — TEST RUN"
echo "================================================"
echo "Job ID:    $SLURM_JOB_ID"
echo "Dataset:   $DATASET"
echo "Encoder:   $TEST_ENCODER (single encoder test)"
echo "Node:      $(hostname)"
echo "Start:     $(date)"
echo "================================================"

# ==================== ENVIRONMENT ====================
module load cuda/12.2

cd "$PROJECT_DIR" || { echo "FAIL: Project directory not found"; exit 1; }
source .venv/bin/activate

set -a
source benchmarks/.env
set +a

echo "Python: $(which python) ($(python --version))"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# ==================== HF TOKEN CHECK ====================
echo ""
echo "Checking HuggingFace token access to gated models..."
python -c "
from huggingface_hub import HfApi, login
import os, sys

token = os.environ.get('HF_TOKEN', '')
if not token:
    print('FAIL: HF_TOKEN not set')
    sys.exit(1)

login(token=token, add_to_git_credential=False)
api = HfApi()

# Test access to all gated models
gated = {
    'paige-ai/Virchow2': 'virchow2',
    'MahmoodLab/UNI2-h': 'uni_v2',
    'bioptimus/H-optimus-1': 'hoptimus1',
    'histai/hibou-L': 'hibou_l',
    'MahmoodLab/conchv1_5': 'conch_v15',
    'bioptimus/H0-mini': 'h0_mini',
}
failed = []
for repo, key in gated.items():
    try:
        api.model_info(repo, token=token)
        print(f'  {key:15s} ({repo}): OK')
    except Exception as e:
        err = str(e).split(chr(10))[0][:100]
        print(f'  {key:15s} ({repo}): DENIED — {err}')
        failed.append(key)

if failed:
    print()
    print(f'FAIL: {len(failed)} gated model(s) inaccessible: {failed}')
    print('Fix: 1) Accept license on each model page  2) Enable gated repo access in HF token settings')
    sys.exit(1)

print('  All gated models accessible.')
" || { echo "FAIL: HF token check failed. Fix your token before running extraction."; exit 1; }

# ==================== RUN ====================
echo ""
echo "Running: segmentation -> patching -> feature extraction ($TEST_ENCODER, 3 slides)"
echo "================================================"

python benchmarks/scripts/run_feature_extraction.py \
    --dataset "$DATASET" \
    --gpu 0 \
    --models "$TEST_ENCODER" \
    --limit 3

EXIT_CODE=$?

# ==================== RESULT ====================
echo ""
echo "================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "TEST PASSED"
else
    echo "TEST FAILED (exit code $EXIT_CODE)"
fi
echo "End time: $(date)"
echo "================================================"

exit $EXIT_CODE
