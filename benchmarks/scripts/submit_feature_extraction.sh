#!/bin/bash
# SLURM job script: WSI feature extraction for CLWD on Fir HPC
#
# Extracts patch-level features from whole-slide images using pathology
# foundation models via TRIDENT. Runs all encoders sequentially on 1 GPU.
#
# Priority order: virchow2, uni_v2, hoptimus1, then hibou_l, conch_v15, midnight12k, h0_mini
#
# Usage:
#   sbatch benchmarks/scripts/submit_feature_extraction.sh

#SBATCH --job-name=clwd_extract
#SBATCH --account=def-wanglab
#SBATCH --time=1-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=12
#SBATCH --gpus=h100:1
#SBATCH --mem=128G
#SBATCH --output=logs/extract_%x_%j.out
#SBATCH --error=logs/extract_%x_%j.err
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=leo.yin@mail.utoronto.ca
#SBATCH --exclude=fc10512

# ==================== CONFIG ====================
DATASET="clwd"
PROJECT_DIR="/home/yinshuol/scratch/autoMIL/autoMIL"

# ==================== JOB INFO ====================
echo "================================================"
echo "AutoBench Feature Extraction — CLWD"
echo "================================================"
echo "Job ID:    $SLURM_JOB_ID"
echo "Dataset:   $DATASET"
echo "Node:      $(hostname)"
echo "GPUs:      $SLURM_GPUS_PER_NODE"
echo "CPUs:      $SLURM_CPUS_PER_TASK"
echo "Start:     $(date)"
echo "================================================"

# ==================== ENVIRONMENT ====================
module load cuda/12.2

cd "$PROJECT_DIR" || { echo "ERROR: Project directory not found"; exit 1; }
source .venv/bin/activate

# Load env vars from .env (HF_TOKEN, WANDB_API_KEY, dataset roots)
set -a
source benchmarks/.env
set +a

echo "Python:    $(which python)"
echo "CUDA:      $(nvcc --version 2>/dev/null | grep release || echo 'N/A')"

# ==================== GPU INFO ====================
echo ""
echo "GPU Information:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# ==================== CUDA CHECK ====================
echo ""
echo "PyTorch CUDA check..."
python -c "
import torch
print(f'  PyTorch {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    print(f'  Driver: {torch.version.cuda}')
else:
    print('  ERROR: CUDA not available — extraction will be extremely slow on CPU!')
    print('  Check: module load cuda version vs PyTorch CUDA version')
    import sys; sys.exit(1)
" || { echo "ERROR: CUDA not available. Aborting."; exit 1; }

# ==================== VALIDATION ====================
echo ""
echo "Validating dataset config..."
python -c "
from autobench.config import load_dataset_config
ds = load_dataset_config('${DATASET}')
print(f'  Dataset:  {ds.name}')
print(f'  WSI dir:  {ds.wsi_dir}')
print(f'  Output:   {ds.output_dir}')
print(f'  Encoders: {list(ds.encoder_models.values())}')
" || { echo "ERROR: Failed to load dataset config"; exit 1; }

# ==================== RUN ====================
echo ""
echo "Starting feature extraction..."
echo "Priority: virchow2 > uni_v2 > hoptimus1 > hibou_l > conch_v15 > midnight12k > h0_mini"
echo "================================================"

python benchmarks/scripts/run_feature_extraction.py \
    --dataset "$DATASET" \
    --gpu 0

EXIT_CODE=$?

# ==================== DONE ====================
echo ""
echo "================================================"
echo "Feature extraction finished"
echo "Exit code: $EXIT_CODE"
echo "End time:  $(date)"
echo "================================================"

exit $EXIT_CODE
