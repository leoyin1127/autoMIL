"""Centralized sys.path management for SMMILe library imports.

SMMILe's single/ directory uses bare module names (e.g. ``from models.model_smmile import ...``),
so we add benchmarks/lib/SMMILe/single/ to sys.path.
"""

import sys

from autobench import LIB_ROOT

_SMMILE_SINGLE_DIR = str(LIB_ROOT / "SMMILe" / "single")

if _SMMILE_SINGLE_DIR not in sys.path:
    sys.path.insert(0, _SMMILE_SINGLE_DIR)

# Re-export SMMILe components for clean imports elsewhere
from models.model_smmile import SMMILe_SINGLE  # noqa: E402, F401
from utils.utils import collate_MIL, make_weights_for_balanced_classes_split  # noqa: E402, F401
