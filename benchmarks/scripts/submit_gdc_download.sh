#!/bin/bash
# SLURM job script: Download TCGA slides from GDC
#
# Downloads .svs files using gdc-client, then flattens into wsi/ directory.
# Runs on CPU node (no GPU needed).
#
# Usage:
#   sbatch benchmarks/scripts/submit_gdc_download.sh <dataset_dir> <manifest>
#   sbatch benchmarks/scripts/submit_gdc_download.sh datasets/TCGA-LUAD datasets/TCGA-LUAD/gdc_manifest_matched.txt

#SBATCH --job-name=gdc_download
#SBATCH --account=def-wanglab
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --output=logs/gdc_download_%j.out
#SBATCH --error=logs/gdc_download_%j.err
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=leo.yin@mail.utoronto.ca

DATASET_DIR="${1:?Usage: sbatch $0 <dataset_dir> <manifest>}"
MANIFEST="${2:?Usage: sbatch $0 <dataset_dir> <manifest>}"

PROJECT_DIR="/home/yinshuol/scratch/autoMIL/autoMIL"
cd "$PROJECT_DIR" || exit 1

echo "================================================"
echo "GDC Slide Download"
echo "================================================"
echo "Job ID:      $SLURM_JOB_ID"
echo "Dataset dir: $DATASET_DIR"
echo "Manifest:    $MANIFEST"
echo "Start:       $(date)"
echo "================================================"

# Count expected downloads
TOTAL=$(tail -n +2 "$MANIFEST" | wc -l)
echo "Slides to download: $TOTAL"

# Download
mkdir -p "${DATASET_DIR}/gdc_download"
/home/yinshuol/bin/gdc-client download \
    -m "$MANIFEST" \
    -d "${DATASET_DIR}/gdc_download/" \
    --n-processes 8

echo ""
echo "Download complete. Flattening to wsi/..."

# Flatten .svs files to wsi/ directory
mkdir -p "${DATASET_DIR}/wsi"
find "${DATASET_DIR}/gdc_download/" -name "*.svs" -exec mv {} "${DATASET_DIR}/wsi/" \;

# Count results
DOWNLOADED=$(ls "${DATASET_DIR}/wsi/"*.svs 2>/dev/null | wc -l)
echo "Downloaded and flattened: $DOWNLOADED / $TOTAL slides"

# Clean up empty UUID directories
rm -rf "${DATASET_DIR}/gdc_download/"

echo ""
echo "================================================"
echo "Done: $(date)"
echo "================================================"
