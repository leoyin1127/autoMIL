"""Generalization gate subpackage (GTE-01..06 / D-135..D-151).

Public surface (populated incrementally across Phase 5 plans):
    05-01: paired_wilcoxon_with_bootstrap, bonferroni_correct, diagnose_gate_health
    05-02: GateManifest, read_manifest, write_manifest, load_manifest, write_manifest_committed
    05-04: nominate
    05-06: evaluate_candidate
    05-07: promote
"""
from __future__ import annotations

import logging

from automil.gate.stats import (
    bonferroni_correct,
    diagnose_gate_health,
    paired_wilcoxon_with_bootstrap,
)

logger = logging.getLogger(__name__)

__all__ = [
    "bonferroni_correct",
    "diagnose_gate_health",
    "paired_wilcoxon_with_bootstrap",
]
