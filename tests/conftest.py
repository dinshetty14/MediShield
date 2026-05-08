"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def dataset_dir(project_root: Path) -> Path:
    """Return the dataset directory."""
    return project_root / "dataset"


@pytest.fixture
def sample_image_path(dataset_dir: Path) -> Path:
    """Return path to a sample test image."""
    # Use first bill image as sample
    sample = dataset_dir / "bill_innovh_01.png"
    if sample.exists():
        return sample
    # Fallback to any image
    for img in dataset_dir.glob("*.png"):
        return img
    pytest.skip("No test images found")


@pytest.fixture
def sample_image_bytes(sample_image_path: Path) -> bytes:
    """Return sample image as bytes."""
    return sample_image_path.read_bytes()
