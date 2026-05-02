"""Coverage for IdentityValidator (REG-03 identity / REG-06 / D-30 / D-31 / D-32)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _torch_available() -> bool:
    try:
        importlib.import_module("torch")
        return True
    except ImportError:
        return False


requires_torch = pytest.mark.skipif(not _torch_available(), reason="torch not installed")


# --- constraints parsing ---

def test_constraints_parsing_happy():
    from automil.registry.validators.identity import (
        IdentityConstraint, IdentityValidator,
    )
    v = IdentityValidator(
        mode="architecture-preserving",
        identity_constraints=("param_count_pct: 5", "output_rank: 2"),
    )
    assert len(v.constraints) == 2
    assert any(c.kind == "param_count_pct" and c.value == "5" for c in v.constraints)
    assert any(c.kind == "output_rank" and c.value == "2" for c in v.constraints)


def test_constraints_parsing_malformed():
    from automil.registry.validators.identity import IdentityValidator
    with pytest.raises(ValueError, match=r"badformat|kind: value|identity_constraints"):
        IdentityValidator(identity_constraints=("badformat",))


def test_constraints_empty_ok():
    from automil.registry.validators.identity import IdentityValidator
    v = IdentityValidator(mode="free", identity_constraints=())
    assert v.constraints == ()


# --- lazy torch import (Plan 01-01 invariant) ---

def test_no_top_level_torch_in_identity_module():
    """Plan 01-01 invariant: the registry must remain importable without torch."""
    path = Path("src/automil/registry/validators/identity.py")
    content = path.read_text()
    offending = []
    in_type_checking = False
    for ln in content.splitlines():
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("if TYPE_CHECKING"):
            in_type_checking = True
            continue
        if in_type_checking and ln and not ln.startswith(" ") and not ln.startswith("\t"):
            in_type_checking = False
        if in_type_checking:
            continue
        if stripped.startswith("import torch") or stripped.startswith("from torch "):
            # Allow inside def or method body — check indentation.
            if not ln.startswith(" ") and not ln.startswith("\t"):
                offending.append(ln)
    assert not offending, f"Top-level torch import found: {offending}"


def test_identity_validator_imports_without_torch():
    """The IdentityValidator class import path must not require torch."""
    # If this import works, lazy import is honoured.
    from automil.registry.validators.identity import IdentityValidator
    assert IdentityValidator is not None


# --- free mode (requires torch) ---

@requires_torch
def test_free_mode_happy_path(tmp_path):
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator

    class Parent(ModelVariant):
        def forward(self, features, coords=None):
            # Returns (batch=1, num_classes=2) float32
            return torch.zeros(1, 2)

    class Variant(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    archive = tmp_path / "archive" / "node_0001"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="free")
    v.check(Variant, Parent, archive)  # no exception
    assert not (archive / "validation_failure.json").exists()


@requires_torch
def test_free_mode_rank_mismatch(tmp_path):
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator
    from automil.registry.errors import ValidationError

    class Parent(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)  # rank 2

    class BadVariant(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(2)  # rank 1

    archive = tmp_path / "archive" / "node_0002"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="free")
    with pytest.raises(ValidationError) as exc_info:
        v.check(BadVariant, Parent, archive)
    err = exc_info.value
    assert err.validator_name == "identity"
    assert "rank" in err.reason.lower()

    # validation_failure.json written.
    report_path = archive / "validation_failure.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert report["validator_name"] == "identity"
    assert report["mode"] == "free"
    assert report["expected"]["rank"] == 2
    assert report["actual"]["rank"] == 1


@requires_torch
def test_free_mode_dtype_mismatch(tmp_path):
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator
    from automil.registry.errors import ValidationError

    class Parent(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2, dtype=torch.float32)

    class BadVariant(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2, dtype=torch.float64)

    archive = tmp_path / "archive" / "node_0003"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="free")
    with pytest.raises(ValidationError, match=r"dtype|float"):
        v.check(BadVariant, Parent, archive)


@requires_torch
def test_free_mode_skips_param_count(tmp_path):
    """Free mode does NOT enforce param-count tolerance."""
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator

    class Parent(ModelVariant):
        def __init__(self):
            self.linear = torch.nn.Linear(10, 2)
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    class HugeVariant(ModelVariant):
        def __init__(self):
            self.linear = torch.nn.Linear(1000, 2)  # 100x more params
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    archive = tmp_path / "archive" / "node_0004"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="free")
    v.check(HugeVariant, Parent, archive)  # passes — free mode permits


# --- architecture-preserving mode ---

@requires_torch
def test_arch_preserving_param_count_happy(tmp_path):
    """4% more params; constraint `param_count_pct: 5` -> passes."""
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator

    class Parent(ModelVariant):
        def __init__(self):
            # Fake "params" via a torch.nn.Module attribute. The validator
            # must use sum(p.numel() for p in module.parameters()) for the
            # count, which works on any nn.Module subclass. For these
            # tests we use a Linear layer with known param count.
            self.linear = torch.nn.Linear(10, 2)  # 10*2 + 2 = 22 params
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)
        def parameters(self):
            yield from self.linear.parameters()

    class GoodVariant(ModelVariant):
        def __init__(self):
            # 22 + ~4% = 22.88, so 23 params (within 5%).
            # Use Linear(10, 2) with one extra unused buffer to bump count by 1.
            self.linear = torch.nn.Linear(10, 2)
            self.extra = torch.nn.Parameter(torch.zeros(1))
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)
        def parameters(self):
            yield from self.linear.parameters()
            yield self.extra

    archive = tmp_path / "archive" / "node_0005"
    archive.mkdir(parents=True)

    v = IdentityValidator(
        mode="architecture-preserving",
        identity_constraints=("param_count_pct: 5",),
    )
    v.check(GoodVariant, Parent, archive)  # passes


@requires_torch
def test_arch_preserving_param_count_fail(tmp_path):
    """30% more params; constraint `param_count_pct: 5` -> hard-fail."""
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator
    from automil.registry.errors import ValidationError

    class Parent(ModelVariant):
        def __init__(self):
            self.linear = torch.nn.Linear(10, 2)  # 22 params
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)
        def parameters(self):
            yield from self.linear.parameters()

    class BigVariant(ModelVariant):
        def __init__(self):
            self.linear = torch.nn.Linear(13, 2)  # 13*2+2 = 28 (~27% more)
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)
        def parameters(self):
            yield from self.linear.parameters()

    archive = tmp_path / "archive" / "node_0006"
    archive.mkdir(parents=True)

    v = IdentityValidator(
        mode="architecture-preserving",
        identity_constraints=("param_count_pct: 5",),
    )
    with pytest.raises(ValidationError, match=r"param_count_pct"):
        v.check(BigVariant, Parent, archive)
    report = json.loads((archive / "validation_failure.json").read_text())
    assert "param_count_pct" in str(report["constraints_evaluated"])


@requires_torch
def test_arch_preserving_no_constraints_degrades_to_dtype_rank(tmp_path):
    """architecture-preserving without identity_constraints runs the same
    dtype + rank check as free mode (graceful degradation)."""
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator

    class Parent(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    class Variant(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    archive = tmp_path / "archive" / "node_0007"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="architecture-preserving", identity_constraints=())
    v.check(Variant, Parent, archive)  # passes


# --- validation_failure.json schema + atomic write ---

@requires_torch
def test_validation_failure_json_schema(tmp_path):
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator
    from automil.registry.errors import ValidationError

    class Parent(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    class BadVariant(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1)

    archive = tmp_path / "archive" / "node_0008"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="free")
    with pytest.raises(ValidationError):
        v.check(BadVariant, Parent, archive)

    report = json.loads((archive / "validation_failure.json").read_text())
    for required in (
        "validator_name", "mode", "variant_class", "parent_class",
        "reason", "expected", "actual", "constraints_evaluated", "timestamp",
    ):
        assert required in report, f"missing key {required!r}"


@requires_torch
def test_validation_failure_json_atomic_write(tmp_path):
    """The temp file pattern from PATTERNS.md §3 — verify no .tmp leftover."""
    import torch
    from automil.registry import ModelVariant
    from automil.registry.validators.identity import IdentityValidator
    from automil.registry.errors import ValidationError

    class Parent(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1, 2)

    class BadVariant(ModelVariant):
        def forward(self, features, coords=None):
            return torch.zeros(1)

    archive = tmp_path / "archive" / "node_0009"
    archive.mkdir(parents=True)

    v = IdentityValidator(mode="free")
    with pytest.raises(ValidationError):
        v.check(BadVariant, Parent, archive)

    # No .tmp file left over from a partial write.
    leftover_tmp = list(archive.glob("validation_failure.json*.tmp"))
    assert leftover_tmp == [], f"unexpected leftover tmp file: {leftover_tmp}"
    # The real file is parseable JSON (not a partial write).
    json.loads((archive / "validation_failure.json").read_text())


def test_validators_init_re_exports_identity():
    from automil.registry.validators import IdentityValidator, InterfaceValidator, PurityValidator
    assert IdentityValidator is not None
    assert InterfaceValidator is not None
    assert PurityValidator is not None
