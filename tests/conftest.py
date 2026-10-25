from __future__ import annotations

from pathlib import Path

import pytest

from idp_agent.config import Settings
from idp_agent.samples import generate_samples


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Offline settings writing into a temp dir, without sleeping between retries."""
    return Settings(output_dir=tmp_path / "out", retry_backoff=0.0)


@pytest.fixture(scope="session")
def data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("data")
    generate_samples(root)
    return root


@pytest.fixture
def samples_dir(data_root: Path) -> Path:
    return data_root / "samples"
