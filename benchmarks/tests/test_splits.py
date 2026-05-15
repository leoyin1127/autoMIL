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


class TestPatientLevelStratification:
    """Splits must keep all slides of one case in the same partition."""

    @pytest.fixture
    def multi_slide_csv(self, tmp_path):
        # 40 cases, 2 slides each (80 slides total). Balanced labels.
        rows = []
        for case_idx in range(40):
            label = "pos" if case_idx % 2 == 0 else "neg"
            for slide_idx in range(2):
                rows.append({
                    "case_id": f"P{case_idx:03d}",
                    "slide_id": f"P{case_idx:03d}_slide{slide_idx}",
                    "label": label,
                })
        csv_path = tmp_path / "multi.csv"
        pd.DataFrame(rows).to_csv(csv_path, index=False)
        return str(csv_path)

    def test_no_case_crosses_train_val_test(self, multi_slide_csv, tmp_path, registries):
        splits_dir = str(tmp_path / "splits_multi")
        strategy_cfg = registries.strategy_registry["standard"]
        create_strategy_splits(
            multi_slide_csv, splits_dir, strategy_cfg, n_splits=4, seed=42,
        )
        src = pd.read_csv(multi_slide_csv)
        slide_to_case = src.set_index("slide_id")["case_id"].to_dict()
        for fold in range(4):
            sdf = pd.read_csv(os.path.join(splits_dir, f"splits_{fold}.csv"))
            train_cases = {slide_to_case[s] for s in sdf["train"].dropna()}
            val_cases = {slide_to_case[s] for s in sdf["val"].dropna()}
            test_cases = {slide_to_case[s] for s in sdf["test"].dropna()}
            assert not (train_cases & val_cases), f"fold {fold}: train∩val cases"
            assert not (train_cases & test_cases), f"fold {fold}: train∩test cases"
            assert not (val_cases & test_cases), f"fold {fold}: val∩test cases"

    def test_both_slides_of_a_case_in_same_partition(self, multi_slide_csv, tmp_path, registries):
        splits_dir = str(tmp_path / "splits_multi")
        strategy_cfg = registries.strategy_registry["standard"]
        create_strategy_splits(
            multi_slide_csv, splits_dir, strategy_cfg, n_splits=4, seed=42,
        )
        src = pd.read_csv(multi_slide_csv)
        slide_to_case = src.set_index("slide_id")["case_id"].to_dict()
        for fold in range(4):
            sdf = pd.read_csv(os.path.join(splits_dir, f"splits_{fold}.csv"))
            for partition_col in ("train", "val", "test"):
                slides = sdf[partition_col].dropna().tolist()
                case_to_slides_here: dict = {}
                for s in slides:
                    case_to_slides_here.setdefault(slide_to_case[s], []).append(s)
                # Every case in this partition should contribute BOTH its slides
                for case, slides_here in case_to_slides_here.items():
                    assert len(slides_here) == 2, (
                        f"fold {fold} {partition_col}: case {case} has only "
                        f"{len(slides_here)} slide(s), expected 2"
                    )

    def test_raises_when_case_id_missing(self, tmp_path, registries):
        df = pd.DataFrame({
            "slide_id": ["s0", "s1", "s2"],
            "label": ["a", "b", "a"],
        })
        csv_path = tmp_path / "no_case.csv"
        df.to_csv(csv_path, index=False)
        splits_dir = str(tmp_path / "splits_nc")
        strategy_cfg = registries.strategy_registry["standard"]
        with pytest.raises(ValueError, match="case_id"):
            create_strategy_splits(
                str(csv_path), splits_dir, strategy_cfg, n_splits=2, seed=42,
            )
