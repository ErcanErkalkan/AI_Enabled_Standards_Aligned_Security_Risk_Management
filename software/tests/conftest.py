import pytest
from unittest import mock
import urllib.request

def pytest_addoption(parser):
    parser.addoption("--offline", action="store_true", default=False, help="run tests without network calls")

@pytest.fixture(autouse=True)
def offline_mode(request, monkeypatch):
    if request.config.getoption("--offline"):
        def _mock_urlopen(*args, **kwargs):
            raise RuntimeError("Network calls are disabled in --offline mode")
        monkeypatch.setattr(urllib.request, "urlopen", _mock_urlopen)
