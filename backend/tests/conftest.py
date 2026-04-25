"""Pytest config for backend tests.

Sets up asyncio mode so @pytest.mark.asyncio works without per-file plugin config.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Auto-enable asyncio mode for all tests in this directory."""
    config.option.asyncio_mode = "auto"
    # Default loop scope for asyncio fixtures (silences DeprecationWarning).
    config.option.asyncio_default_fixture_loop_scope = "function"
