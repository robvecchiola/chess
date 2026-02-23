from app import create_app
import config


def test_create_app_defaults_to_development_when_env_missing(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    app = create_app()

    assert app.config["DEBUG"] is True
    assert app.config["TESTING"] is False


def test_create_app_uses_testing_config_when_env_testing(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()

    assert app.config["TESTING"] is True
    assert app.config["DEBUG"] is True


def test_create_app_uses_production_config_when_env_production(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(config.ProductionConfig, "SECRET_KEY", "prod-secret-key")
    monkeypatch.setattr(config.ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")

    app = create_app()

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SECRET_KEY"] == "prod-secret-key"
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
