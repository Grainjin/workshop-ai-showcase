"""Release boundaries: full CI dependency, fail-closed cloud requests and owned reset."""

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tomllib

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    path = ROOT / ".github/workflows" / name
    assert path.is_file(), f"Missing release workflow: {name}"
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def test_preview_handoff_requires_complete_existing_ci():
    preview = workflow("deploy-preview.yml")
    ci = workflow("ci.yml")
    assert "workflow_call" in ci["on"]
    assert set(ci["jobs"]) == {
        "backend", "mobile", "public-copy", "case-study-site", "case-study-e2e",
    }
    assert preview["jobs"]["ci"]["uses"] == "./.github/workflows/ci.yml"
    for name, job in preview["jobs"].items():
        if name != "ci":
            assert job["needs"] == "ci", f"{name} bypasses full CI"
    assert "pull_request_target" not in preview["on"]


@pytest.mark.parametrize("private", ["true", "false"])
def test_external_preview_request_refuses_even_with_token_and_environment(tmp_path, private):
    job = workflow("deploy-preview.yml")["jobs"]["external-deploy-disabled"]
    assert "environment" not in job  # Absent environments may auto-create unprotected.
    summary = tmp_path / "summary"
    result = subprocess.run(
        ["bash", "-e", "-c", job["steps"][0]["run"]],
        cwd=ROOT, capture_output=True, text=True,
        env={"PATH": os.defpath, "GITHUB_STEP_SUMMARY": str(summary),
             "RAILWAY_TOKEN": "test-token-never-print", "REPOSITORY_PRIVATE": private,
             "DEPLOY_ENVIRONMENT": "preview", "APPROVAL_VERIFIED": "true"},
    )
    assert result.returncode != 0
    assert "disabled" in result.stdout.lower()
    assert "test-token-never-print" not in result.stdout + result.stderr + summary.read_text()


def test_manual_reset_has_only_disposable_postgres_and_no_cloud_credentials():
    reset = workflow("demo-reset.yml")
    assert set(reset["on"]) == {"workflow_dispatch"}
    assert reset["permissions"] == {"contents": "read"}
    job = reset["jobs"]["isolated-reset-check"]
    assert "environment" not in job
    assert job["services"]["postgres"]["env"]["POSTGRES_DB"] == "workshop_demo_reset_dry_run"
    assert job["env"]["WORKSHOP_DATABASE_URL"] == (
        "postgresql+psycopg://workshop:workshop@127.0.0.1:5432/workshop_demo_reset_dry_run"
    )
    assert job["env"]["DEMO_MODE"] == "true"
    assert job["env"]["DEMO_DATABASE_MARKER"] == "workshop_demo"
    for value in job["env"].values():
        assert "${{" not in value  # No platform/repository environment injected into dry run.


def test_native_reset_is_short_lived_and_uses_existing_guarded_cli():
    path = ROOT / "railway-reset.toml"
    assert path.is_file(), "Missing native private-network reset configuration"
    config = tomllib.loads(path.read_text())
    assert config["build"]["dockerfilePath"] == "docker/api/Dockerfile"
    deploy = config["deploy"]
    assert deploy["cronSchedule"] == "0 17 * * *"
    assert deploy["restartPolicyType"] == "NEVER"
    assert "healthcheckPath" not in deploy
    assert "preDeployCommand" not in deploy
    args = shlex.split(deploy["startCommand"])
    args = [arg.replace("/app/", f"{ROOT}/") for arg in args]
    result = subprocess.run(
        ["sh", *args], cwd=ROOT, capture_output=True, text=True,
        env={"PATH": f"{Path(sys.executable).parent}:{os.defpath}",
             "WORKSHOP_PUBLIC_DEPLOYMENT": "false", "DEMO_MODE": "false",
             "WORKSHOP_PAYMENT_MODE": "demo", "DEMO_DATABASE_MARKER": "workshop_demo",
             "WORKSHOP_DATABASE_URL": "postgresql+psycopg://localhost/workshop_demo_not_connected"},
    )
    assert result.returncode == 1
    assert "no reset was committed" in result.stderr
    assert result.stdout == ""


def test_manual_reset_summary_cannot_report_success_on_failure(tmp_path):
    steps = workflow("demo-reset.yml")["jobs"]["isolated-reset-check"]["steps"]
    summary_step = next(step for step in steps if step.get("name") == "Record dry-run outcome")
    assert summary_step["if"] == "always()"
    for outcome in ("success", "failure", "cancelled"):
        summary = tmp_path / f"summary-{outcome}"
        result = subprocess.run(
            ["bash", "-e", "-c", summary_step["run"]], cwd=ROOT,
            capture_output=True, text=True,
            env={"PATH": os.defpath, "RESET_OUTCOME": outcome,
                 "GITHUB_STEP_SUMMARY": str(summary)},
        )
        assert result.returncode == 0
        message = summary.read_text()
        assert outcome in message
        assert "No cloud database was accessed" in message
        if outcome != "success":
            assert "passed" not in message.lower()
