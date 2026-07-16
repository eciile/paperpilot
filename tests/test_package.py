"""Tests for the top-level PaperPilot package."""

import paperpilot


def test_package_version() -> None:
    """The package should expose its current version."""
    assert paperpilot.__version__ == "0.1.0"