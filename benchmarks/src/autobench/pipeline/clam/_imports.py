"""Centralized CLAM imports with sys.path management.

CLAM is not installed as a package — it lives at benchmarks/lib/CLAM/.
This module adds it to sys.path once and re-exports the components we need,
so no other module has to touch sys.path.
"""

import sys

from autobench import LIB_ROOT

_CLAM_DIR = str(LIB_ROOT / "CLAM")

if _CLAM_DIR not in sys.path:
    sys.path.insert(0, _CLAM_DIR)

# Models
from models.model_clam import CLAM_SB, CLAM_MB  # noqa: E402
from models.model_mil import MIL_fc  # noqa: E402

# Dataset
from dataset_modules.dataset_generic import (  # noqa: E402
    Generic_MIL_Dataset,
    Generic_Split,
    save_splits,
)

# Utilities
from utils.utils import (  # noqa: E402
    collate_MIL,
    get_optim,
    get_split_loader,
    make_weights_for_balanced_classes_split,
    print_network,
)

# Training / evaluation (core pipeline)
from utils.core_utils import (  # noqa: E402
    EarlyStopping,
    train as clam_train,
    train_loop,
    train_loop_clam,
    validate,
    validate_clam,
    summary,
)

# Evaluation utilities (model loading from checkpoint)
from utils.eval_utils import initiate_model  # noqa: E402

__all__ = [
    "CLAM_SB",
    "CLAM_MB",
    "MIL_fc",
    "Generic_MIL_Dataset",
    "Generic_Split",
    "save_splits",
    "collate_MIL",
    "get_optim",
    "get_split_loader",
    "make_weights_for_balanced_classes_split",
    "print_network",
    "EarlyStopping",
    "clam_train",
    "train_loop",
    "train_loop_clam",
    "validate",
    "validate_clam",
    "summary",
    "initiate_model",
]
