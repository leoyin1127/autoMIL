"""AutoBench — MIL benchmark suite for computational pathology."""

from pathlib import Path

# Root of the benchmarks/ directory (parent of src/autobench/)
BENCHMARKS_ROOT = Path(__file__).resolve().parents[2]

# External library directory (benchmarks/lib/)
LIB_ROOT = BENCHMARKS_ROOT / "lib"
