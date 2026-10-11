"""Demo configuration validates deployment input before serving requests."""

import runpy
import os
import json
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import config


DEMO_ENV_KEYS = (
    "DEMO_MODE",
    "WORKSHOP_PAYMENT_MODE",
    "DEMO_AI_DAILY_LIMIT",
    "DEMO_AI_PER_MINUTE_LIMIT",
    "DEMO_DATABASE_MARKER",
    "WORKSHOP_DEMO_SEED",
)


@pytest.fixture
def load_config(monkeypatch):
    # Execute in an isolated namespace: existing API imports retain their config.
    # Disable dotenv input so developer-local credentials/settings cannot leak in.
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    for name in DEMO_ENV_KEYS:
        monkeypatch.delenv(name, raising=False)

    def load(**values):
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        return runpy.run_path(str(Path(config.__file__)))

    return load


def test_demo_defaults_keep_normal_mode(load_config):
    settings = load_config()
    assert settings["DEMO_MODE"] is False
    assert settings["PAYMENT_MODE"] == "iyzico_sandbox"
    assert settings["DEMO_AI_DAILY_LIMIT"] == 100
    assert settings["DEMO_AI_PER_MINUTE_LIMIT"] == 10
    assert settings["DEMO_DATABASE_MARKER"] == "workshop_demo"
    assert settings["WORKSHOP_DEMO_SEED"] == 42


def test_unconfigured_mail_uses_non_deliverable_sender(load_config, monkeypatch):
    for name in ("WORKSHOP_SMTP_USERNAME", "WORKSHOP_EMAIL_FROM", "WORKSHOP_EMAIL_BACKEND"):
        monkeypatch.delenv(name, raising=False)
    settings = load_config()
    assert settings["EMAIL_FROM"].endswith("@example.invalid")
    assert settings["SMTP_USERNAME"].endswith("@example.invalid")
    assert settings["EMAIL_BACKEND"] == "console"


def test_explicit_smtp_sender_and_transport_are_preserved(load_config):
    settings = load_config(WORKSHOP_EMAIL_BACKEND="smtp", WORKSHOP_SMTP_HOST="smtp.example.invalid",
                           WORKSHOP_SMTP_USERNAME="operator@example.invalid",
                           WORKSHOP_EMAIL_FROM="sender@example.invalid")
    assert settings["EMAIL_BACKEND"] == "smtp"
    assert settings["SMTP_HOST"] == "smtp.example.invalid"
    assert settings["SMTP_USERNAME"] == "operator@example.invalid"
    assert settings["EMAIL_FROM"] == "sender@example.invalid"


@pytest.mark.parametrize("configured", [False, True])
def test_compose_mail_defaults_are_non_deliverable_with_explicit_override_preserved(configured):
    root = Path(config.__file__).resolve().parents[1]
    env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]}
    if configured:
        env.update(WORKSHOP_SMTP_USERNAME="operator@example.invalid", WORKSHOP_EMAIL_FROM="sender@example.invalid")
    result = subprocess.run(["docker", "compose", "--env-file", "/dev/null", "config", "--format", "json"],
                            cwd=root, env=env, capture_output=True, text=True, check=True)
    settings = json.loads(result.stdout)["services"]["api"]["environment"]
    assert settings["WORKSHOP_SMTP_USERNAME"] == ("operator@example.invalid" if configured else "workshop-demo@example.invalid")
    assert settings["WORKSHOP_EMAIL_FROM"] == ("sender@example.invalid" if configured else "workshop-demo@example.invalid")


@pytest.mark.parametrize("value", ["true", "TRUE", " true ", "1", "yes", "YES", "on"])
def test_demo_mode_accepts_true_values(load_config, value):
    assert load_config(DEMO_MODE=value)["DEMO_MODE"] is True


@pytest.mark.parametrize("value", ["false", "FALSE", " false ", "0", "no", "NO", "off"])
def test_demo_mode_accepts_false_values(load_config, value):
    assert load_config(DEMO_MODE=value)["DEMO_MODE"] is False


@pytest.mark.parametrize("value", ["", " ", "enabled", "2"])
def test_demo_mode_rejects_invalid_values_at_load(load_config, value):
    with pytest.raises(ValueError, match="DEMO_MODE"):
        load_config(DEMO_MODE=value)


def test_boolean_parser_uses_typed_default(load_config):
    parser = load_config()["get_bool_config"]
    assert parser("UNSET_DEMO_TEST_FLAG", True) is True
    assert parser("UNSET_DEMO_TEST_FLAG", False) is False


@pytest.mark.parametrize("value", ["iyzico_sandbox", "demo"])
def test_payment_mode_accepts_supported_modes(load_config, value):
    assert load_config(WORKSHOP_PAYMENT_MODE=value)["PAYMENT_MODE"] == value


@pytest.mark.parametrize("value", ["", " ", "live", "IYZICO_SANDBOX", "unknown"])
def test_payment_mode_rejects_unknown_modes_at_load(load_config, value):
    with pytest.raises(ValueError, match="WORKSHOP_PAYMENT_MODE"):
        load_config(WORKSHOP_PAYMENT_MODE=value)


@pytest.mark.parametrize("name", ["DEMO_AI_DAILY_LIMIT", "DEMO_AI_PER_MINUTE_LIMIT"])
def test_demo_quota_accepts_positive_integer(load_config, name):
    assert load_config(**{name: " 1 "})[name] == 1


@pytest.mark.parametrize("name", ["DEMO_AI_DAILY_LIMIT", "DEMO_AI_PER_MINUTE_LIMIT"])
@pytest.mark.parametrize("value", ["", " ", "0", "-1", "1.5", "many"])
def test_demo_quota_rejects_invalid_values_at_load(load_config, name, value):
    with pytest.raises(ValueError, match=name):
        load_config(**{name: value})


def test_database_marker_is_trimmed(load_config):
    assert load_config(DEMO_DATABASE_MARKER=" custom_demo ")["DEMO_DATABASE_MARKER"] == "custom_demo"


@pytest.mark.parametrize("value", ["", " ", "\t"])
def test_database_marker_rejects_empty_values_at_load(load_config, value):
    with pytest.raises(ValueError, match="DEMO_DATABASE_MARKER"):
        load_config(DEMO_DATABASE_MARKER=value)


@pytest.mark.parametrize("value, expected", [("0", 0), ("-7", -7), (" 123 ", 123)])
def test_demo_seed_accepts_integer(load_config, value, expected):
    assert load_config(WORKSHOP_DEMO_SEED=value)["WORKSHOP_DEMO_SEED"] == expected


@pytest.mark.parametrize("value", ["", " ", "4.2", "random"])
def test_demo_seed_rejects_non_integer_at_load(load_config, value):
    with pytest.raises(ValueError, match="WORKSHOP_DEMO_SEED"):
        load_config(WORKSHOP_DEMO_SEED=value)


def test_demo_helper_hides_disabled_mode(monkeypatch):
    from backend.utils.demo_mode import is_demo_mode, require_demo_mode

    monkeypatch.setattr(config, "DEMO_MODE", False)
    assert is_demo_mode() is False
    with pytest.raises(HTTPException) as error:
        require_demo_mode()
    assert error.value.status_code == 404
    assert error.value.detail == "Not found"


def test_demo_helper_allows_enabled_mode(monkeypatch):
    from backend.utils.demo_mode import is_demo_mode, require_demo_mode

    monkeypatch.setattr(config, "DEMO_MODE", True)
    assert is_demo_mode() is True
    assert require_demo_mode() is None
