from app.core.config import CORS_ORIGINS


def test_expected_frontend_origins_are_explicitly_allowed():
    assert "http://191.252.181.8:3009" in CORS_ORIGINS
    assert "http://localhost:3009" in CORS_ORIGINS
    assert "http://127.0.0.1:3009" in CORS_ORIGINS
