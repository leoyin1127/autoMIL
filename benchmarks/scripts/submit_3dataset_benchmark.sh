#!/bin/bash
# Submit benchmark jobs for CLWD, CCRCC, and hancock datasets.
#
# Models: clam_mb (CLAM) + simple_mil (nnMIL)
# Encoders: hoptimus1, uni_v2, virchow2
# Tasks: subtype_7class (CLWD), pbrm1 + high_grade (CCRCC),
#        tumor_site + survival + treatment_outcome (hancock)
#
# Usage:
#   bash benchmarks/scripts/submit_3dataset_benchmark.sh
#
# Total: 36 experiments, 180 fold trainings across 3 datasets.

set -euo pipefail

PROJECT_DIR="/home/yinshuol/scratch/autoMIL/autoMIL"
cd "$PROJECT_DIR"
mkdir -p logs

# Common config
export ENCODERS="hoptimus1 uni_v2 virchow2"
export MODELS="clam_mb"
export NNMIL_MODELS="simple_mil"

echo "=============================================="
echo "3-Dataset Benchmark Submission"
echo "  Encoders: $ENCODERS"
echo "  CLAM models: $MODELS"
echo "  nnMIL models: $NNMIL_MODELS"
echo "  Frameworks: clam nnmil (default)"
echo "=============================================="
echo ""

declare -A DATASET_TASKS
DATASET_TASKS[clwd]="subtype_7class"
DATASET_TASKS[ccrcc]="pbrm1 high_grade"
DATASET_TASKS[hancock]="tumor_site survival treatment_outcome"

JOB_IDS=()
DATASETS=(clwd ccrcc hancock)

for ds in "${DATASETS[@]}"; do
    tasks="${DATASET_TASKS[$ds]}"
    JOB_ID=$(DATASET="$ds" TASKS="$tasks" sbatch --parsable \
        --job-name="bench_${ds}" \
        --time=1-00:00:00 \
        benchmarks/scripts/submit_benchmark.sh)
    JOB_IDS+=("$JOB_ID")
    echo "  $ds (tasks: $tasks): job $JOB_ID"
done

echo ""
echo "All 3 jobs submitted. Monitor with:"
echo "  squeue -u $USER"
echo ""
echo "Log files:"
for i in "${!DATASETS[@]}"; do
    ds="${DATASETS[$i]}"
    jid="${JOB_IDS[$i]}"
    echo "  $ds: tail -f logs/bench_bench_${ds}_${jid}.out"
done
