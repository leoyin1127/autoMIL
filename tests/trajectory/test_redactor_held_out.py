"""Tests for held-out node-id redaction in trajectory/redactor.py (D-139 / GTE-01).

Verifies:
  - Held-out node IDs are replaced with <HELD_OUT> placeholder
  - Non-held-out IDs are not touched (no false positives)
  - mtime-keyed cache invalidates when graph.json changes
  - Soft-fail when no automil/ project is present
  - redact_event walks dicts and redacts string leaves
  - Static patterns (_PATTERNS) still apply after the extension
"""
from __future__ import annotations

import json
import os
import time

import pytest

from automil.trajectory.redactor import (
    _held_out_ids_cached,
    redact,
    redact_event,
)


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear lru_cache between tests so prior fixtures don't leak mtime state."""
    _held_out_ids_cached.cache_clear()
    yield
    _held_out_ids_cached.cache_clear()


@pytest.fixture
def held_out_project(tmp_path, monkeypatch):
    """tmp_path/automil/ with graph.json having node_0099 as held-out."""
    adir = tmp_path / "automil"
    adir.mkdir()
    (adir / "config.yaml").write_text("# fixture\n")
    graph = {
        "nodes": {
            "node_0050": {"id": "node_0050", "metadata": {}},
            "node_0099": {"id": "node_0099", "metadata": {"held_out": True}},
        }
    }
    (adir / "graph.json").write_text(json.dumps(graph))
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def empty_held_out_project(tmp_path, monkeypatch):
    """tmp_path/automil/ with graph.json having NO held-out nodes."""
    adir = tmp_path / "automil"
    adir.mkdir()
    (adir / "config.yaml").write_text("# fixture\n")
    graph = {
        "nodes": {
            "node_0042": {"id": "node_0042", "metadata": {}},
        }
    }
    (adir / "graph.json").write_text(json.dumps(graph))
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---- Test 1: no held-out nodes => passthrough --------------------------------

def test_redact_no_held_out_passthrough(empty_held_out_project):
    """With zero held_out=true nodes, non-held-out node IDs are untouched."""
    result = redact("node_0042 was the parent")
    assert result == "node_0042 was the parent"


# ---- Test 2: held-out ID replaced ------------------------------------------

def test_redact_replaces_held_out_node_id(held_out_project):
    """node_0099 is held-out; it must be replaced with <HELD_OUT>."""
    result = redact("eval finished for node_0099")
    assert result == "eval finished for <HELD_OUT>"


# ---- Test 3: mixed — preserve non-held-out, redact held-out ----------------

def test_redact_preserves_non_held_out(held_out_project):
    """node_0050 is NOT held-out; node_0099 is. Only the held-out one is replaced."""
    result = redact("node_0050 beat node_0099")
    assert result == "node_0050 beat <HELD_OUT>"


# ---- Test 4: redact_event walks dict ----------------------------------------

def test_redact_event_walks_dict(held_out_project):
    """redact_event replaces held-out IDs in all string leaves; ints pass through."""
    event = {"msg": "node_0099 done", "id": "node_0099", "n": 42}
    result = redact_event(event)
    assert result["msg"] == "<HELD_OUT> done"
    assert result["id"] == "<HELD_OUT>"
    assert result["n"] == 42  # non-string passes through unchanged


# ---- Test 5: static patterns still work ------------------------------------

def test_redact_static_patterns_still_work(held_out_project):
    """Pre-existing static patterns (sk- etc.) are preserved after extension."""
    result = redact("sk-Abcdefghij1234567890key")
    assert result == "sk-[REDACTED]"


# ---- Test 6: cache invalidates on mtime change ------------------------------

def test_held_out_cache_invalidates_on_mtime_change(tmp_path, monkeypatch):
    """Adding a new held-out node to graph.json invalidates the mtime cache."""
    adir = tmp_path / "automil"
    adir.mkdir()
    (adir / "config.yaml").write_text("# fixture\n")

    graph_path = adir / "graph.json"

    # Initial: only node_0099 is held-out
    graph1 = {
        "nodes": {
            "node_0099": {"id": "node_0099", "metadata": {"held_out": True}},
        }
    }
    graph_path.write_text(json.dumps(graph1))
    monkeypatch.chdir(tmp_path)

    result1 = redact("node_0099 node_0077")
    assert result1 == "<HELD_OUT> node_0077", f"Initial redaction failed: {result1!r}"

    # Advance mtime so the lru_cache key changes
    new_mtime = graph_path.stat().st_mtime + 1.0
    os.utime(str(graph_path), (new_mtime, new_mtime))

    # Add node_0077 as held-out
    graph2 = {
        "nodes": {
            "node_0099": {"id": "node_0099", "metadata": {"held_out": True}},
            "node_0077": {"id": "node_0077", "metadata": {"held_out": True}},
        }
    }
    graph_path.write_text(json.dumps(graph2))
    # Bump mtime again after rewrite so new content is picked up
    new_mtime2 = new_mtime + 1.0
    os.utime(str(graph_path), (new_mtime2, new_mtime2))

    result2 = redact("node_0099 node_0077")
    assert result2 == "<HELD_OUT> <HELD_OUT>", f"Cache did not invalidate: {result2!r}"


# ---- Test 7: soft-fail when no automil/ project present --------------------

def test_redact_handles_missing_graph(tmp_path, monkeypatch):
    """When no automil/config.yaml is found, static patterns still apply; node IDs pass through."""
    # chdir to a dir with no automil/config.yaml so _find_automil_dir() raises
    monkeypatch.chdir(tmp_path)
    # sk- token needs 20+ chars after prefix: "secretsecret12345678" = 20 chars
    result = redact("node_0099 sk-secretsecret12345678key")
    # Static pattern fires; node_0099 NOT redacted (soft-fail: no graph available)
    assert "sk-[REDACTED]" in result
    assert "node_0099" in result  # NOT replaced when graph unavailable
