"""Shared pytest fixtures for hwp-edit-mcp tests."""

import os
import shutil
import sys
from pathlib import Path

import pytest

# Real documents are personal, so they live in a git-ignored folder (or HWP_TEST_SAMPLES).
DEFAULT_SAMPLES_DIR = Path(__file__).resolve().parent / "local_samples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def get_samples_dir() -> Path:
    return Path(os.environ.get("HWP_TEST_SAMPLES", str(DEFAULT_SAMPLES_DIR)))


@pytest.fixture
def sample_hwp_copy(tmp_path: Path) -> Path:
    src = FIXTURES_DIR / "sample_form.hwp"
    dst = tmp_path / src.name
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def sample_hwpx_copy(tmp_path: Path) -> Path:
    src = FIXTURES_DIR / "sample_form.hwpx"
    dst = tmp_path / src.name
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def personal_hwp_copy(tmp_path: Path) -> Path:
    # HWP_TEST_SAMPLES may point to one .hwp file or to a folder (first *.hwp is used).
    samples = get_samples_dir()
    if samples.is_file():
        preferred = samples
    elif samples.is_dir():
        hwp_files = sorted(samples.glob("*.hwp"))
        if not hwp_files:
            pytest.skip(f"No .hwp sample files in: {samples}")
        preferred = hwp_files[0]
    else:
        pytest.skip(f"HWP_TEST_SAMPLES not found: {samples}")

    dst = tmp_path / preferred.name
    shutil.copy2(preferred, dst)
    return dst
