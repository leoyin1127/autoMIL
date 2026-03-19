"""Tests for strategy-aware splits."""

import os

import numpy as np
import pandas as pd
import pytest

from autobench.pipeline.config import (
    build_registries,
)
from autobench.pipeline.splits import create_strategy_splits
from _helpers import make_test_ds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ds():
    return make_test_ds()


@pytest.fixture
def registries(ds):
    return build_registries(ds)


@pytest.fixture
def mapping_csv(tmp_path):
    """Create a mapping CSV with slides."""
    rows = []
    for i in range(80):
        rows.append({
            "new_name": f"slide_{i:05d}.svs",
            "status": "mapped_unique_case_id",
            "primary_case_id": f"P{i:03d}",
            "BRCA_predict_label": i % 2,
            "HRD_label": i % 3,
        })
    csv_path = tmp_path / "mapping.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return str(csv_path)


@pytest.fixture
def task_csv(tmp_path, mapping_csv, ds):
    """Create a simple task CSV without cohort column."""
    df = pd.read_csv(mapping_csv)
    df = df[df["status"] == "mapped_unique_case_id"].reset_index(drop=True)
    df = df.dropna(subset=["BRCA_predict_label"]).reset_index(drop=True)
    task_df = pd.DataFrame({
        "case_id": df["primary_case_id"],
        "slide_id": df["new_name"].str.replace(".svs", "", regex=False),
        "label": df["BRCA_predict_label"].astype(int).map({0: "neg", 1: "pos"}),
    })
    csv_path = tmp_path / "brca.csv"
    task_df.to_csv(csv_path, index=False)
    return str(csv_path)


# ---------------------------------------------------------------------------
# Standard 5-fold
# ---------------------------------------------------------------------------


class TestStandardCV:
    def test_creates_split_files(self, task_csv, tmp_path, registries):
        splits_dir = str(tmp_path / "splits_std")
        strategy_cfg = registries.strategy_registry["standard"]
        paths = create_strategy_splits(
            task_csv, splits_dir, strategy_cfg, n_splits=3, seed=42,
        )
        assert len(paths) == 3
        for p in paths:
            assert os.path.isfile(p)

    def test_no_overlap_between_splits(self, task_csv, tmp_path, registries):
        splits_dir = str(tmp_path / "splits_std")
        strategy_cfg = registries.strategy_registry["standard"]
        create_strategy_splits(
            task_csv, splits_dir, strategy_cfg, n_splits=3, seed=42,
        )
        for fold in range(3):
            df = pd.read_csv(os.path.join(splits_dir, f"splits_{fold}.csv"))
            train = set(df["train"].dropna())
            val = set(df["val"].dropna())
            test = set(df["test"].dropna())
            assert len(train & val) == 0
            assert len(train & test) == 0
            assert len(val & test) == 0

    def test_all_slides_in_test_exactly_once(self, task_csv, tmp_path, registries):
        splits_dir = str(tmp_path / "splits_std")
        strategy_cfg = registries.strategy_registry["standard"]
        n_splits = 3
        create_strategy_splits(
            task_csv, splits_dir, strategy_cfg, n_splits=n_splits, seed=42,
        )
        all_test = []
        for fold in range(n_splits):
            df = pd.read_csv(os.path.join(splits_dir, f"splits_{fold}.csv"))
            all_test.extend(df["test"].dropna().tolist())
        task_df = pd.read_csv(task_csv)
        assert set(all_test) == set(task_df["slide_id"])

    def test_works_without_cohort_column(self, task_csv, tmp_path, registries):
        splits_dir = str(tmp_path / "splits_no_cohort")
        strategy_cfg = registries.strategy_registry["standard"]
        paths = create_strategy_splits(
            task_csv, splits_dir, strategy_cfg, n_splits=3, seed=42,
        )
        assert len(paths) == 3

    def test_reproducible(self, task_csv, tmp_path, registries):
        dir1 = str(tmp_path / "s1")
        dir2 = str(tmp_path / "s2")
        strategy_cfg = registries.strategy_registry["standard"]
        create_strategy_splits(task_csv, dir1, strategy_cfg, n_splits=3, seed=42)
        create_strategy_splits(task_csv, dir2, strategy_cfg, n_splits=3, seed=42)
        for fold in range(3):
            df1 = pd.read_csv(os.path.join(dir1, f"splits_{fold}.csv"))
            df2 = pd.read_csv(os.path.join(dir2, f"splits_{fold}.csv"))
            assert df1.equals(df2)
