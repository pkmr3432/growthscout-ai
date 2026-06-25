# tests/conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: Mark test as requiring live external API connections"
    )
