"""Generalization gate subpackage (GTE-01..06 / D-135..D-151).

Public surface (populated incrementally across Phase 5 plans):
    05-01: paired_wilcoxon_with_bootstrap, bonferroni_correct, diagnose_gate_health
    05-02: GateManifest, read_manifest, write_manifest, load_manifest, write_manifest_committed,
           retire_manifest, validate_manifest_dict
    05-04: nominate
    05-06: evaluate_candidate
    05-07: promote
"""
from __future__ import annotations

import logging

from automil.gate.evaluate import evaluate_candidate
from automil.gate.manifest import (
    GateManifest,
    load_manifest,
    read_manifest,
    retire_manifest,
    validate_manifest_dict,
    write_manifest,
    write_manifest_committed,
)
from automil.gate.nominate import nominate
from automil.gate.stats import (
    bonferroni_correct,
    diagnose_gate_health,
    paired_wilcoxon_with_bootstrap,
)

logger = logging.getLogger(__name__)

__all__ = [
    "GateManifest",
    "bonferroni_correct",
    "diagnose_gate_health",
    "evaluate_candidate",
    "load_manifest",
    "nominate",
    "paired_wilcoxon_with_bootstrap",
    "read_manifest",
    "retire_manifest",
    "validate_manifest_dict",
    "write_manifest",
    "write_manifest_committed",
]
