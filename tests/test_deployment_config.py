"""Execute deployment boundaries; don't infer behavior from shell source text."""

import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tomllib

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def startup(tmp_path):
    """Replace only external processes; the shell and validation run unchanged."""
    commands = tmp_path / "bin"
    commands.mkdir()
    events = tmp_path / "events.jsonl"
    adapter = commands / "adapter"
    adapter.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "name = Path(sys.argv[0]).name\n"
        "args = sys.argv[1:]\n"
        "if name == 'python' and args and args[0].endswith('validate_public_config.py'):\n"
        "    os.execv(sys.executable, [sys.executable, *args])\n"
        "with open(os.environ['EVENTS'], 'a') as output:\n"
        "    output.write(json.dumps([name, *args]) + '\\n')\n"
        "if name == 'alembic':\n"
        "    sys.exit(int(os.environ.get('MIGRATION_EXIT', '0')))\n",
        encoding="utf-8",
    )
    adapter.chmod(0o755)
    for name in ("python", "alembic", "uvicorn", "celery"):
        (commands / name).symlink_to(adapter)

    def run(role="api", *, command=None, public=True, **changes):
        env = {
            "PATH": f"{commands}:{os.defpath}",
            "EVENTS": str(events),
            "WORKSHOP_PUBLIC_DEPLOYMENT": "true" if public else "false",
            "DEMO_MODE": "true",
            "WORKSHOP_PAYMENT_MODE": "demo",
            "WORKSHOP_CORS_ORIGINS": "https://demo.example.com,https://case.example.com",
            "WORKSHOP_JWT_PRIVATE_KEY": "test-provisioned-private",
            "WORKSHOP_JWT_PUBLIC_KEY": "test-provisioned-public",
            "PORT": "9123",
            **changes,
        }
        if command:
            args = ["sh", "-c", command.replace("/app/", f"{ROOT}/")]
        else:
            args = ["sh", str(ROOT / "docker/api/entrypoint.sh"), role]
        result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
        calls = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        return result, calls

    return run


def test_public_restart_only_starts_api_on_assigned_port(startup):
    result, calls = startup(WORKSHOP_SEED="1")
    assert result.returncode == 0, result.stderr
    assert calls == [["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9123"]]


def test_local_compose_start_still_migrates_and_seeds(startup):
    result, calls = startup(public=False, WORKSHOP_SEED="1", PORT="8000")
    assert result.returncode == 0, result.stderr
    assert calls == [
        ["python", "scripts/generate_jwt_keys.py"],
        ["alembic", "upgrade", "head"],
        ["python", "-m", "backend.seed_locations"],
        ["python", "-m", "backend.seed_demo_data"],
        ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
    ]


def test_failed_local_migration_never_seeds_or_starts(startup):
    result, calls = startup(public=False, MIGRATION_EXIT="23", WORKSHOP_SEED="1")
    assert result.returncode == 23
    assert calls == [["python", "scripts/generate_jwt_keys.py"], ["alembic", "upgrade", "head"]]


@pytest.mark.parametrize("exit_code", [0, 23])
def test_release_only_runs_migration_and_propagates_failure(startup, exit_code):
    result, calls = startup("release", MIGRATION_EXIT=str(exit_code))
    assert result.returncode == exit_code, result.stderr
    assert calls == [["alembic", "upgrade", "head"]]


@pytest.mark.parametrize("changes", [
    {"DEMO_MODE": "false"}, {"DEMO_MODE": ""},
    {"WORKSHOP_PAYMENT_MODE": "iyzico_sandbox"},
    {"WORKSHOP_CORS_ORIGINS": ""},
    {"WORKSHOP_CORS_ORIGINS": "https://demo.example.com,http://remote.example.com"},
    {"WORKSHOP_CORS_ORIGINS": "https://demo.example.com/path"},
    {"WORKSHOP_CORS_ORIGINS": "https://demo.example.com/"},
    {"WORKSHOP_CORS_ORIGINS": "https://user:password@demo.example.com"},
    {"WORKSHOP_CORS_ORIGINS": "*"},
    {"WORKSHOP_JWT_PRIVATE_KEY": "", "WORKSHOP_JWT_PUBLIC_KEY": "",
     "WORKSHOP_JWT_PRIVATE_KEY_PATH": "/nonexistent/private.pem",
     "WORKSHOP_JWT_PUBLIC_KEY_PATH": "/nonexistent/public.pem"},
])
def test_public_start_refuses_unsafe_configuration_before_any_side_effect(startup, changes):
    result, calls = startup(**changes)
    assert result.returncode != 0
    assert calls == []
    assert "password@" not in result.stderr


def test_public_worker_does_not_generate_keys_or_seed(startup):
    result, calls = startup("worker")
    assert result.returncode == 0, result.stderr
    assert calls == [["celery", "-A", "backend.tasks.celery_app", "worker", "--loglevel=info"]]


def test_reset_mode_forwards_arguments_to_existing_guarded_command(startup):
    # No real database/reset is reached by this process boundary fixture.
    result, calls = startup(command=f"sh {ROOT}/docker/api/entrypoint.sh reset-demo --confirm reset-workshop-demo")
    assert result.returncode == 0, result.stderr
    assert calls == [["python", "-m", "backend.reset_demo_data", "--confirm", "reset-workshop-demo"]]


def test_railway_contract_separates_release_and_public_start(startup):
    path = ROOT / "railway.toml"
    assert path.exists(), "Railway deployment contract is absent"
    settings = tomllib.loads(path.read_text())
    assert settings["build"]["dockerfilePath"] == "docker/api/Dockerfile"
    deploy = settings["deploy"]
    assert deploy["healthcheckPath"] == "/health"
    command = deploy["preDeployCommand"][0]
    result, calls = startup(command=command, MIGRATION_EXIT="23")
    assert result.returncode == 23
    assert calls == [["alembic", "upgrade", "head"]]
    result, calls = startup(command=deploy["startCommand"], WORKSHOP_SEED="1")
    assert result.returncode == 0, result.stderr
    assert calls[-1] == ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9123"]
    assert len(calls) == 2  # Only the preceding release attempt and this API process.


@pytest.mark.parametrize("root,build", [("frontend/mobile", "EXPO_PUBLIC_PUBLIC_DEPLOYMENT=true npm run build:web"), ("showcase/site", "npm run build")])
def test_static_project_contract_handles_direct_spa_navigation(root, build):
    path = ROOT / root / "vercel.json"
    assert path.exists(), "Independent Vercel project configuration is absent"
    settings = json.loads(path.read_text())
    assert settings["buildCommand"] == build
    assert settings["outputDirectory"] == "dist"
    assert settings["rewrites"] == [{"source": "/(.*)", "destination": "/index.html"}]


def test_local_worker_disables_api_only_image_health_probe():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert compose["services"]["worker"].get("healthcheck", {}).get("disable") is True


@pytest.fixture
def frontend_config():
    node = shutil.which("node")
    compiler = ROOT / "frontend/mobile/node_modules/typescript"
    if not node or not compiler.is_dir():
        pytest.skip("Frontend integration requires Node and frontend/mobile npm dependencies")
    script = """
const fs = require('fs'), ts = require(process.argv[1]), vm = require('vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const exports = {};
vm.runInNewContext(code, { exports, process, URL, require: () => ({ Platform: { OS: 'web' } }) });
const chatCode = ts.transpileModule(fs.readFileSync(process.argv[3], 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const chat = {};
vm.runInNewContext(chatCode, { exports: chat, require: (name) => {
  if (name === '../config/env') return exports;
  // HTTP request/session setup has no effect on the real pure WebSocket URL builders.
  if (name === './client') return {};
  throw new Error(`Unexpected chat module dependency: ${name}`);
} });
console.log(JSON.stringify({ ...exports, userWebSocketUrl: chat.buildUserWebSocketUrl(),
  chatWebSocketUrl: chat.buildChatWebSocketUrl(17) }));
"""

    def run(**changes):
        env = {"EXPO_PUBLIC_PUBLIC_DEPLOYMENT": "true", "EXPO_PUBLIC_DEMO_MODE": "true",
               "EXPO_PUBLIC_API_BASE_URL": "https://api.example.com",
               "EXPO_PUBLIC_WS_BASE_URL": "wss://api.example.com", **changes}
        return subprocess.run([node, "-e", script, str(compiler), str(ROOT / "frontend/mobile/src/config/env.ts"),
                               str(ROOT / "frontend/mobile/src/api/chat.ts")],
                              env=env, capture_output=True, text=True)

    return run


def test_public_frontend_uses_explicit_secure_endpoints(frontend_config):
    result = frontend_config()
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["API_BASE_URL"] == "https://api.example.com"
    assert json.loads(result.stdout)["WS_BASE_URL"] == "wss://api.example.com"


@pytest.mark.parametrize("suffix", ["", "/"])
def test_public_origins_build_valid_user_and_chat_websocket_routes(frontend_config, suffix):
    result = frontend_config(EXPO_PUBLIC_API_BASE_URL="https://api.example.com" + suffix,
                             EXPO_PUBLIC_WS_BASE_URL="wss://api.example.com" + suffix)
    assert result.returncode == 0, result.stderr
    endpoints = json.loads(result.stdout)
    assert endpoints["userWebSocketUrl"] == "wss://api.example.com/ws/me"
    assert endpoints["chatWebSocketUrl"] == "wss://api.example.com/ws/chats/17"
    assert endpoints["API_BASE_URL"] == "https://api.example.com"


@pytest.mark.parametrize("changes", [
    {"EXPO_PUBLIC_API_BASE_URL": ""}, {"EXPO_PUBLIC_API_BASE_URL": "same-origin"},
    {"EXPO_PUBLIC_API_BASE_URL": "http://remote.example.com"},
    {"EXPO_PUBLIC_API_BASE_URL": "https://user:password@api.example.com"},
    {"EXPO_PUBLIC_WS_BASE_URL": ""}, {"EXPO_PUBLIC_WS_BASE_URL": "ws://remote.example.com"},
    {"EXPO_PUBLIC_DEMO_MODE": "false"},
])
def test_public_frontend_refuses_missing_or_insecure_endpoints(frontend_config, changes):
    result = frontend_config(**changes)
    assert result.returncode != 0
    assert "password@" not in result.stderr


@pytest.mark.parametrize("api,ws,expected_api", [
    ("same-origin", "same-origin", ""),
    ("http://127.0.0.1:8000", "ws://127.0.0.1:8000", "http://127.0.0.1:8000"),
])
def test_local_frontend_keeps_http_and_same_origin_modes(frontend_config, api, ws, expected_api):
    result = frontend_config(EXPO_PUBLIC_PUBLIC_DEPLOYMENT="false", EXPO_PUBLIC_API_BASE_URL=api,
                             EXPO_PUBLIC_WS_BASE_URL=ws, EXPO_PUBLIC_DEMO_MODE="false")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["API_BASE_URL"] == expected_api
    if expected_api:
        assert json.loads(result.stdout)["userWebSocketUrl"] == "ws://127.0.0.1:8000/ws/me"


@pytest.mark.parametrize("changes,expected", [({}, 0), ({"EXPO_PUBLIC_API_BASE_URL": "http://remote.example.com"}, 1),
    ({"EXPO_PUBLIC_WS_BASE_URL": ""}, 1), ({"EXPO_PUBLIC_PUBLIC_DEPLOYMENT": "false"}, 0),
    ({"EXPO_PUBLIC_API_BASE_URL": "https://api.example.com/", "EXPO_PUBLIC_WS_BASE_URL": "wss://api.example.com/"}, 0)])
def test_web_export_checks_public_config_before_bundling(changes, expected):
    node = shutil.which("node")
    if not node:
        pytest.skip("Web export preflight integration requires Node")
    env = {"EXPO_PUBLIC_PUBLIC_DEPLOYMENT": "true", "EXPO_PUBLIC_DEMO_MODE": "true",
           "EXPO_PUBLIC_API_BASE_URL": "https://api.example.com",
           "EXPO_PUBLIC_WS_BASE_URL": "wss://api.example.com", **changes}
    result = subprocess.run([node, "scripts/validate-public-env.cjs"], cwd=ROOT / "frontend/mobile",
                            env=env, capture_output=True, text=True)
    assert result.returncode == expected, result.stderr


@pytest.mark.parametrize("status,expected", [(200, 0), (503, 1)])
def test_container_healthcheck_probes_assigned_port_without_migration(tmp_path, status, expected):
    path = ROOT / "docker/api/healthcheck.py"
    assert path.exists(), "Container health probe is absent"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status if self.path == "/health" else 404)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([sys.executable, str(path)], env={"PORT": str(server.server_port)},
                                capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
