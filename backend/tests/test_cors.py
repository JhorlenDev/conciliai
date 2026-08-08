import re

from app.core.config import CORS_ORIGINS, CORS_ORIGIN_REGEX


def test_expected_frontend_origins_are_explicitly_allowed():
    assert "http://192.168.1.99:3009" in CORS_ORIGINS
    assert "http://localhost:3009" in CORS_ORIGINS
    assert "http://127.0.0.1:3009" in CORS_ORIGINS


def test_localhost_origins_are_allowed_on_any_dev_port():
    assert re.match(CORS_ORIGIN_REGEX, "http://localhost:3009")
    assert re.match(CORS_ORIGIN_REGEX, "http://127.0.0.1:3010")
