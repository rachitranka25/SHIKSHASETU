"""Unit tests for core configuration."""

import os

import pytest

from backend.core.config import Settings, settings


def test_settings_initialization():
    """Test settings are initialized properly."""
    assert settings.APP_NAME == "ShikshaSetu AI Education API"
    assert settings.APP_VERSION == "4.0.0"
    assert settings.API_V1_PREFIX == "/api/v2"  # V2 API


def test_settings_directories_created():
    """Test that required directories are created on init."""
    assert settings.UPLOAD_DIR.exists()
    assert settings.MODEL_CACHE_DIR.exists()
    assert settings.LOG_DIR.exists()


def test_settings_environment_defaults():
    """Test default environment values."""
    assert os.getenv("HOST", "0.0.0.0") == settings.HOST
    assert int(os.getenv("PORT", "8000")) == settings.PORT


def test_settings_rate_limiting():
    """Test rate limiting configuration."""
    assert settings.RATE_LIMIT_PER_MINUTE >= 60  # At least 60/min
    assert settings.RATE_LIMIT_PER_HOUR >= 1000  # At least 1000/hour
    assert hasattr(settings, "RATE_LIMIT_STORAGE")  # Storage backend configured


def test_settings_password_requirements():
    """Test password requirements are configured."""
    assert settings.MIN_PASSWORD_LENGTH >= 8  # Minimum 8 chars
    assert hasattr(settings, "PASSWORD_REQUIRE_UPPERCASE")
    assert hasattr(settings, "PASSWORD_REQUIRE_LOWERCASE")
    assert hasattr(settings, "PASSWORD_REQUIRE_DIGIT")


# ==================== PRODUCTION STARTUP VALIDATION ====================


def _production_settings(monkeypatch, **overrides) -> Settings:
    """
    A hardened production Settings instance, with overrides applied last.

    Settings resolves most values from the environment when the module is
    imported, so the production checks are exercised by flipping attributes on
    an instance rather than by reimporting the module.
    """
    monkeypatch.setenv("JWT_SECRET_KEY", "k" * 64)
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:pw@localhost/shiksha")

    config = Settings()
    config.ENVIRONMENT = "production"
    config.DEBUG = False
    config.RATE_LIMIT_ENABLED = True
    config.ALLOWED_ORIGINS = ["https://shikshasetu.example"]
    config.ALLOW_CREDENTIALS = True

    for name, value in overrides.items():
        setattr(config, name, value)

    return config


def test_hardened_production_config_has_no_blocking_issues(monkeypatch):
    """The baseline the other cases deviate from must itself be clean."""
    issues: list[str] = []
    _production_settings(monkeypatch)._validate_production_env(issues)

    assert issues == []


def test_production_rejects_disabled_rate_limiting(monkeypatch):
    """Unlimited login attempts is a brute-force invitation."""
    issues: list[str] = []
    _production_settings(monkeypatch, RATE_LIMIT_ENABLED=False)._validate_production_env(
        issues
    )

    assert any(i.startswith("ERROR") and "RATE_LIMIT_ENABLED" in i for i in issues)


def test_production_rejects_wildcard_origin_with_credentials(monkeypatch):
    """Any site could then read authenticated responses."""
    issues: list[str] = []
    _production_settings(
        monkeypatch, ALLOWED_ORIGINS=["*"], ALLOW_CREDENTIALS=True
    )._validate_production_env(issues)

    assert any(i.startswith("ERROR") and "ALLOWED_ORIGINS" in i for i in issues)


def test_production_only_warns_on_wildcard_origin_without_credentials(monkeypatch):
    """Still loose, but not a credential leak — a warning, not a hard stop."""
    issues: list[str] = []
    _production_settings(
        monkeypatch, ALLOWED_ORIGINS=["*"], ALLOW_CREDENTIALS=False
    )._validate_production_env(issues)

    assert any(i.startswith("WARNING") and "ALLOWED_ORIGINS" in i for i in issues)
    assert not any(i.startswith("ERROR") for i in issues)


def test_production_requires_jwt_secret(monkeypatch):
    """Test a missing signing key is fatal, not merely logged."""
    config = _production_settings(monkeypatch)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    issues: list[str] = []
    config._validate_production_env(issues)

    assert any(i.startswith("ERROR") and "JWT_SECRET_KEY" in i for i in issues)


def test_production_warns_on_debug(monkeypatch):
    """DEBUG leaks internals through error responses."""
    issues: list[str] = []
    _production_settings(monkeypatch, DEBUG=True)._validate_production_env(issues)

    assert any("DEBUG" in i for i in issues)


def test_development_skips_production_checks(monkeypatch):
    """Local work must not be blocked by production-only requirements."""
    config = _production_settings(
        monkeypatch, ENVIRONMENT="development", RATE_LIMIT_ENABLED=False, DEBUG=True
    )

    issues: list[str] = []
    config._validate_production_env(issues)

    assert issues == []


def test_enforce_startup_config_aborts_a_broken_production_boot(monkeypatch):
    """
    The guard the API startup depends on. validate_required() used to only
    log, and nothing called it at all, so a production deploy with rate
    limiting off would have come up silently.
    """
    config = _production_settings(monkeypatch, RATE_LIMIT_ENABLED=False)

    with pytest.raises(RuntimeError, match="RATE_LIMIT_ENABLED"):
        config.enforce_startup_config()


def test_enforce_startup_config_allows_a_hardened_production_boot(monkeypatch):
    """No ERROR-level issues means startup proceeds."""
    config = _production_settings(monkeypatch)

    assert not any(i.startswith("ERROR") for i in config.enforce_startup_config())


def test_enforce_startup_config_is_advisory_in_development(monkeypatch):
    """Same broken config, development environment: reported, not fatal."""
    config = _production_settings(
        monkeypatch, ENVIRONMENT="development", RATE_LIMIT_ENABLED=False
    )

    config.enforce_startup_config()  # must not raise
