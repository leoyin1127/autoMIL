# Phase 07 Deferred Items

## Out-of-Scope Pre-existing Issues Discovered During 07-10

### RecordingBackend missing healthcheck() implementation

**File:** tests/gate/test_evaluate.py
**Error:** `TypeError: Can't instantiate abstract class RecordingBackend with abstract method healthcheck`
**Root cause:** Plan 07-03 added `healthcheck()` as an abstract method to `Backend` ABC. The `RecordingBackend` test stub in `tests/gate/test_evaluate.py` was not updated to implement the new abstract method.
**Impact:** 3 test errors in test_evaluate.py (pre-existing before 07-10).
**Resolution:** Add a stub `healthcheck()` implementation to `RecordingBackend` that returns a minimal `HealthReport` with `detection_status="ok"`. This is a trivial fix, deferred to the next plan that touches the gate tests.
