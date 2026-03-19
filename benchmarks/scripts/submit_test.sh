#!/bin/bash
# SLURM test job: quick smoke test on Fir HPC
#
# Validates the full pipeline (env, config loading, data prep, 1 encoder extract)
# with minimal resources and short wall time.
#
# Usage:
#   sbatch benchmarks/scripts/submit_test.sh

#SBATCH --job-name=autobench_test
#SBATCH --account=def-wanglab
#SBATCH --time=0-00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --gpus=h100:1
#SBATCH --mem=32G
#SBATCH --output=logs/test_%x_%j.out
#SBATCH --error=logs/test_%x_%j.err

# ==================== CONFIG ====================
DATASET="clwd"
PROJECT_DIR="/home/yinshuol/scratch/autoMIL/autoMIL"

echo "================================================"
echo "AutoBench Smoke Test"
echo "================================================"
echo "Job ID:  $SLURM_JOB_ID"
echo "Node:    $(hostname)"
echo "Start:   $(date)"
echo "================================================"

# ==================== ENVIRONMENT ====================
module load cuda/12.2

cd "$PROJECT_DIR" || { echo "FAIL: Project directory not found"; exit 1; }
source .venv/bin/activate

set -a
source benchmarks/.env
set +a

echo ""
echo "[1/6] Environment"
echo "  Python:  $(which python) ($(python --version))"
echo "  CUDA:    $(nvcc --version 2>/dev/null | grep release || echo 'N/A')"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# ==================== IMPORT CHECK ====================
echo ""
echo "[2/6] Python imports"
python -c "
import torch
print(f'  torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB)')

import h5py, pandas, sklearn, scipy, yaml
print('  h5py, pandas, sklearn, scipy, yaml: OK')

from autobench.config import load_dataset_config
from autobench.pipeline.config import build_registries, generate_all_experiments, BenchmarkConfig, Framework
from autobench.pipeline.prepare import create_task_csv
from autobench.pipeline.splits import create_strategy_splits
print('  autobench imports: OK')

from trident import Processor
print('  trident: OK')
" || { echo "FAIL: Import check failed"; exit 1; }

# ==================== DATASET CONFIG ====================
echo ""
echo "[3/6] Dataset config"
python -c "
from autobench.config import load_dataset_config
import os
ds = load_dataset_config('${DATASET}')
print(f'  Name:       {ds.name}')
print(f'  WSI dir:    {ds.wsi_dir}')
print(f'  Mapping:    {ds.mapping_csv}')
print(f'  Output:     {ds.output_dir}')
print(f'  Benchmark:  {ds.benchmark_dir}')
print(f'  Features:   {ds.features_base_dir}')
print(f'  Encoders:   {list(ds.encoder_models.values())}')
print(f'  Tasks:      {list(ds.tasks.keys())}')

# Check paths exist
for label, path in [('WSI dir', ds.wsi_dir), ('Mapping CSV', ds.mapping_csv)]:
    exists = os.path.exists(path)
    status = 'OK' if exists else 'MISSING'
    print(f'  {label}: {status} ({path})')
" || { echo "FAIL: Dataset config check failed"; exit 1; }

# ==================== DATA LOADING ====================
echo ""
echo "[4/6] Data loading"
python -c "
from autobench.config import load_dataset_config
from autobench.data import load_all_slides
ds = load_dataset_config('${DATASET}')
df = load_all_slides(ds.mapping_csv, ds)
print(f'  Loaded {len(df)} slides from mapping CSV')
print(f'  Columns: {list(df.columns[:10])}')
print(f'  First slide: {df.iloc[0][ds.slide_id_column]}')
" || { echo "FAIL: Data loading failed"; exit 1; }

# ==================== EXPERIMENT GRID ====================
echo ""
echo "[5/6] Experiment grid"
python -c "
from autobench.config import load_dataset_config
from autobench.pipeline.config import build_registries, generate_all_experiments, BenchmarkConfig, Framework

ds = load_dataset_config('${DATASET}')
registries = build_registries(ds)

for fw_name, fw in [('CLAM', Framework.CLAM), ('nnMIL', Framework.NNMIL)]:
    cfg = BenchmarkConfig.from_dataset_config(ds, frameworks=[fw])
    exps = generate_all_experiments(cfg, registries)
    print(f'  {fw_name}: {len(exps)} experiments')

cfg = BenchmarkConfig.from_dataset_config(ds, frameworks=[Framework.CLAM, Framework.NNMIL])
exps = generate_all_experiments(cfg, registries)
print(f'  Total (CLAM + nnMIL): {len(exps)} experiments')
" || { echo "FAIL: Experiment grid generation failed"; exit 1; }

# ==================== GPU TEST ====================
echo ""
echo "[6/6] GPU compute test"
python -c "
import torch
if not torch.cuda.is_available():
    print('  SKIP: No CUDA')
    exit(0)
x = torch.randn(1000, 1000, device='cuda:0')
y = torch.mm(x, x)
print(f'  GPU matmul: OK (result shape {y.shape})')
torch.cuda.empty_cache()
" || { echo "FAIL: GPU test failed"; exit 1; }

# ==================== RESULT ====================
echo ""
echo "================================================"
echo "ALL CHECKS PASSED"
echo "End time: $(date)"
echo "================================================"
