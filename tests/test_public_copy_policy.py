"""Exercise the publication gate against real, isolated Git indexes."""

import subprocess
import sys
from pathlib import Path

import pytest

LEGACY_MERGE_REVISION = "0006_merge_ws" + "91_ws" + "98"


@pytest.fixture
def repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def track(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    subprocess.run(["git", "-C", str(root), "add", "-f", "--", name], check=True)
    return path


def scan(root):
    from scripts.check_public_copy import scan_public_copy

    return scan_public_copy(root)


@pytest.mark.parametrize(
    "content,rule",
    [
        ("WS" + "-123 fixes registration", "source-reference"),
        ("ws" + "-123 fixes registration", "source-reference"),
        ("ws" + "123 fixes registration", "source-reference"),
        ("PR" + " #42 adds login", "source-reference"),
        ("pr" + " #42 adds login", "source-reference"),
        ("https://github.com/acme/app/pull" + "/42", "source-reference"),
        ("Every P" + "R needs this evidence.", "source-reference"),
        ("Nothing in this " + "branch contains it.", "source-reference"),
        ("Until it " + "merges, only name exists.", "source-reference"),
        ("See the Ji" + "ra board", "source-reference"),
        ("In this pull" + " request", "source-reference"),
        ("Sprint" + " 2 deliverable", "source-reference"),
        ("From the course " + "team project", "source-reference"),
        ("https://github.com/COMP5703-" + "TUT04-GROUP02/WorkShop-AI", "source-reference"),
        ("api_key = '" + "sk-" + "Ab9x" * 12 + "'", "secret-value"),
        ("token: '" + "ghp_" + "Ab9x" * 10 + "'", "secret-value"),
        ("secret_key = '" + "A1b2C3d4" * 5 + "'", "secret-value"),
        ("-----BEGIN " + "RSA PRIVATE KEY-----", "private-key"),
    ],
)
def test_detects_policy_violations_with_location(repository, content, rule):
    track(repository, "src/example.py", "# Header\n" + content + "\n")
    findings = scan(repository)
    assert [(str(f.file), f.line, f.rule) for f in findings] == [("src/example.py", 2, rule)]


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "NOTICE.md",
        "docs/release/import-manifest.md",
    ],
)
def test_only_approved_notices_allow_source_references(repository, path):
    track(repository, path, "WS" + "-123; PR" + " #42; course " + "team project\n")
    assert scan(repository) == []


@pytest.mark.parametrize(
    "path",
    [
        "docs/README.md",
        "nested/NOTICE.md",
        "docs/import-manifest.md",
        "showcase/index.html",
        "tests/example.py",
        "scripts/example.py",
    ],
)
def test_source_reference_allowlist_does_not_expand_to_other_files(repository, path):
    track(repository, path, "WS" + "-123\n")
    assert [f.rule for f in scan(repository)] == ["source-reference"]


def test_nested_readme_is_not_allowlisted_when_scanning_subdirectory(repository):
    track(repository, "docs/README.md", "WS" + "-123\n")

    findings = scan(repository / "docs")

    assert [(str(f.file), f.rule) for f in findings] == [("README.md", "source-reference")]


@pytest.mark.parametrize("path", ["README.md", "NOTICE.md", "docs/release/import-manifest.md"])
def test_notices_are_still_checked_for_secrets(repository, path):
    secret = "sk-" + "Ab9x" * 12
    track(repository, path, secret)
    findings = scan(repository)
    assert [f.rule for f in findings] == ["secret-value"]
    assert secret not in repr(findings)


def test_environment_template_rejects_unquoted_secret_values(repository):
    secret = "A1b2C3d4" * 5
    track(repository, ".env.example", "LLM_API_KEY=" + secret + "\n")
    assert [f.rule for f in scan(repository)] == ["secret-value"]


def test_accepts_harmless_production_environment_example(repository):
    track(repository, "backend/.env.production.example", "DEMO_MODE=true\nLLM_API_KEY=\n")
    assert scan(repository) == []


@pytest.mark.parametrize("content", [
    "LLM_API_KEY=" + "A1b2C3d4" * 5,
    'JWT_SECRET_KEY="' + "Cedar!Cloud-" + 'River_88-Long"',
    "# embedded " + "sk-" + "Ab9x" * 12,
])
def test_production_example_rejects_and_redacts_secrets(repository, content):
    track(repository, "frontend/.env.production.example", content + "\n")
    findings = scan(repository)
    assert [f.rule for f in findings] == ["secret-value"]
    assert content not in repr(findings)
    assert all("[REDACTED]" in f.excerpt for f in findings)


@pytest.mark.parametrize(
    "path,line",
    [
        ("config.py", 'DB_PASSWORD = "' + "Cedar!Cloud-" + 'River_88-Long"'),
        (
            ".env.example",
            'JWT_SECRET_KEY="' + "eyJhbGciOi" + "JIUzI1NiJ9." + "payload.signature!" + '"',
        ),
    ],
)
def test_rejects_quoted_secret_literals_with_ordinary_punctuation(repository, path, line):
    track(repository, path, line + "\n")

    findings = scan(repository)

    assert [(str(f.file), f.rule) for f in findings] == [(path, "secret-value")]


def test_storage_key_identifiers_are_not_credentials(repository):
    track(repository, "auth.ts", 'const ACCESS_TOKEN_KEY = "workshop_ai_access_token";\n')
    assert scan(repository) == []


def test_variable_references_are_not_secret_literals(repository):
    track(repository, "config.py", "EMBEDDING_API_KEY = _llm.embedding_api_key\n")
    track(repository, "auth.ts", "current_password: payload.currentPassword,\n")
    assert scan(repository) == []


def test_redacts_entire_line_even_when_another_rule_matches(repository):
    secret = "private-value-" + "Ab9x" * 12
    track(repository, "config.py", "# WS" + "-123\napi_key = '" + secret + "' # PR" + " #42\n")
    findings = scan(repository)
    assert {f.rule for f in findings} == {"source-reference", "secret-value"}
    assert secret not in repr(findings)
    assert all("[REDACTED]" in f.excerpt for f in findings)


@pytest.mark.parametrize("name", [".env", "backend/.env.production", "frontend/.env.local"])
def test_rejects_tracked_environment_files_without_echoing_contents(repository, name):
    track(repository, name, "DO_NOT_PRINT_ME=confidential")
    findings = scan(repository)
    assert [f.rule for f in findings] == ["environment-file"]
    assert "confidential" not in repr(findings)


@pytest.mark.parametrize(
    "name,content",
    [
        ("backup.sql", "-- exported database\n"),
        ("database.dump", b"PGDMP\x00private records"),
        ("backend/data.sqlite3", b"SQLite format 3\x00private records"),
        ("backups/db.sql.gz", b"\x1f\x8b\x00private records"),
    ],
)
def test_rejects_database_exports_even_when_binary(repository, name, content):
    track(repository, name, content)
    assert [f.rule for f in scan(repository)] == ["database-dump"]


def test_skips_binary_unknown_extensions_untracked_files_and_symlinks(repository, tmp_path):
    forbidden = "WS" + "-123"
    track(repository, "image.png", forbidden)
    track(repository, "binary.py", forbidden.encode() + b"\x00\xff")
    track(repository, "invalid.txt", forbidden.encode() + b"\xff")
    (repository / "untracked.md").write_text(forbidden)
    (repository / "link.py").symlink_to(repository / "untracked.md")
    subprocess.run(["git", "-C", str(repository), "add", "link.py"], check=True)
    assert scan(repository) == []


def test_allows_templates_product_terms_and_stable_migration_identifiers(repository):
    track(repository, ".env.example", "LLM_API_KEY=\nPASSWORD=your-password\n")
    track(
        repository,
        f"migrations/versions/{LEGACY_MERGE_REVISION}.py",
        f"revision = '{LEGACY_MERGE_REVISION}'\ndown_revision = ('0004_user_names_terms', '0005_customer_addresses')\n",
    )
    track(
        repository, "docs/api.md", "RS256 JWT; ISO 8601; Xcode team; support team; code review.\n"
    )
    assert scan(repository) == []


def test_cli_exit_codes_and_redaction(repository):
    script = Path(__file__).resolve().parents[1] / "scripts/check_public_copy.py"
    clean = subprocess.run(
        [sys.executable, str(script), str(repository)], capture_output=True, text=True
    )
    assert clean.returncode == 0, clean.stderr
    secret = "sk-" + "Ab9x" * 12
    track(repository, "config.py", "api_key = '" + secret + "'\n")
    dirty = subprocess.run(
        [sys.executable, str(script), str(repository)], capture_output=True, text=True
    )
    assert dirty.returncode == 1
    assert "config.py:1: secret-value" in dirty.stdout
    assert secret not in dirty.stdout + dirty.stderr


@pytest.mark.parametrize("path", [
    "docs/testing/ws" + "-92/image.png", "tests/test_ws" + "101.py",
    "docs/testing/WS" + "-92/image.png", "tests/test_WS" + "101.py",
])
def test_rejects_ticket_paths_even_for_binary_assets(repository, path):
    track(repository, path, b"\x00\xff")
    assert [(str(f.file), f.rule) for f in scan(repository)] == [(path, "source-reference-path")]


def test_migration_identifier_exception_does_not_allow_ticket_prose_or_other_paths(repository):
    migration = f"migrations/versions/{LEGACY_MERGE_REVISION}.py"
    track(repository, migration, f"revision = '{LEGACY_MERGE_REVISION}'\n# ws" + "-91 detail\n")
    track(repository, "tests/test_ws" + "91.py", "# functional check\n")
    assert [(str(f.file), f.line, f.rule) for f in scan(repository)] == [
        (migration, 2, "source-reference"),
        ("tests/test_ws" + "91.py", 1, "source-reference-path"),
    ]


def test_migration_reference_is_allowed_only_in_exact_revision_assignment(repository):
    track(repository, "migrations/versions/0007_booking_title.py", f"down_revision = '{LEGACY_MERGE_REVISION}'\n")
    assert scan(repository) == []
    track(repository, "docs/example.md", LEGACY_MERGE_REVISION + "\n")
    assert [f.rule for f in scan(repository)] == ["source-reference"]


def test_embedded_image_payload_is_not_ticket_prose_but_adjacent_caption_is(repository):
    payload = 'image="data:image/png,AAA/ws' + '7/AAA=="'
    track(repository, "diagram.drawio", payload)
    assert scan(repository) == []
    track(repository, "diagram.drawio", payload + ' caption="ws' + '-92"')
    assert [f.rule for f in scan(repository)] == ["source-reference"]
