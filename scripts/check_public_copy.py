"""Check tracked publication content without printing credentials or private records.

Only the three provenance notices may describe the source project. That exception
does not apply to credentials, private keys, environment files or database exports.
Paths are checked too; only explicitly listed immutable migration identifiers are exempt.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


SOURCE_REFERENCE_ALLOWLIST = frozenset(
    {
        "README.md",
        "NOTICE.md",
        "docs/release/import-manifest.md",
    }
)
TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".cjs",
        ".mjs",
        ".jsx",
        ".ts",
        ".tsx",
        ".md",
        ".mdx",
        ".rst",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".html",
        ".css",
        ".scss",
        ".sh",
        ".bash",
        ".xml",
        ".svg",
        ".drawio",
        ".mako",
        ".pem",
        ".key",
        ".csv",
        ".tsv",
    }
)
TEXT_NAMES = frozenset({"Dockerfile", "README", "NOTICE", "LICENSE", ".gitignore", ".dockerignore"})
ENVIRONMENT_EXAMPLE_NAMES = frozenset({".env.example", ".env.production.example"})
SOURCE_REFERENCE = re.compile(
    r"(?i:\bpr\s*#?\s*\d+\b)|/pull/\d+\b|\bPR(?=[\s.,;:]|$)|"
    r"(?i:\bji[r]a\b|\bpull[ -]request\b|\bthis\s+PR\b|\bsprint\s+\d+\b|"
    r"\b(?:course|original|source)\s+team\s+project\b|"
    r"\b(?:later|this)\s+ticket\b|\b(?:backend|branch)\s+merges\b|\bnot\s+merged\b|"
    r"\bthis\s+branch\b|\buntil\s+it\s+merges\b|"
    r"COMP5703[-]TUT04[-]GROUP02)|课程[团]队项目|原[团]队仓库"
)
# Do not mistake the WebSocket package's semantic version or protocol constants
# for a ticket. Underscore-delimited ticket names in tests/migrations still match.
TICKET_REFERENCE = re.compile(r"(?<![A-Za-z0-9])ws-?\d+(?![A-Za-z0-9]|\.\d)", re.IGNORECASE)
EMBEDDED_IMAGE = re.compile(r"data:image/(?:png|jpe?g|gif|webp)(?:;base64)?,[A-Za-z0-9+/=]+")
IMMUTABLE_MIGRATION_REVISION = "0006_merge_ws" + "91_ws" + "98"
IMMUTABLE_MIGRATION_PATH = f"migrations/versions/{IMMUTABLE_MIGRATION_REVISION}.py"
IMMUTABLE_MIGRATION_ASSIGNMENTS = {
    IMMUTABLE_MIGRATION_PATH: ("revision", IMMUTABLE_MIGRATION_REVISION),
    "migrations/versions/0007_booking_title.py": ("down_revision", IMMUTABLE_MIGRATION_REVISION),
}


def _is_immutable_revision_assignment(path: str, line: str) -> bool:
    expected = IMMUTABLE_MIGRATION_ASSIGNMENTS.get(path)
    if expected is None:
        return False
    name, identifier = expected
    return bool(re.fullmatch(
        rf"\s*{name}\s*=\s*(['\"]){re.escape(identifier)}\1\s*", line
    ))


PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
SECRET_TOKEN = re.compile(
    r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
    r"github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|"
    r"AIza[A-Za-z0-9_-]{30,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"
)
SECRET_ASSIGNMENT = re.compile(
    r"\b[\w]*(?:api[_-]?key|secret(?:[_-]?key)?|password|access[_-]?token|refresh[_-]?token)"
    r"\b\s*[:=]\s*(?P<quote>[\"'])(?P<value>[A-Za-z0-9_~!@#$%^&*()+={}\[\]:;,.?/|\\=-]{20,})(?P=quote)",
    re.IGNORECASE,
)
ENV_SECRET_ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?[\w]*(?:KEY|SECRET|PASSWORD|TOKEN)\s*=\s*(?:"
    r"(?P<quote>[\"'])(?P<value>[A-Za-z0-9_~!@#$%^&*()+={}\[\]:;,.?/|\\=-]{20,})(?P=quote)|"
    r"(?P<bare>[A-Za-z0-9_~!@#$%^&*()+={}\[\]:;,.?/|\\=-]{20,}))\s*$",
    re.IGNORECASE,
)
VARIABLE_REFERENCE = re.compile(
    r"(?:\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\}|"
    r"(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*)"
)
DATABASE_EXPORT = re.compile(
    r"\.(?:sql|dump|db|sqlite3?|bak)(?:\.(?:gz|bz2|xz|zip))?$", re.IGNORECASE
)


@dataclass(frozen=True)
class PolicyFinding:
    file: Path
    line: int
    rule: str
    excerpt: str


def scan_public_copy(root: Path) -> list[PolicyFinding]:
    """Inspect working-tree contents of tracked paths, without following symlinks.

    Filename checks run before binary filtering so a binary database cannot bypass
    the gate. Excerpts redact the whole line, including co-located unknown secrets.
    Ignored/untracked local state is outside this publication check's scope.
    """
    root = root.resolve()
    repository_root = Path(
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ).resolve()
    tracked = (
        subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached"],
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8", errors="surrogateescape")
        .split("\0")
    )
    findings = []
    for name in sorted(set(filter(None, tracked))):
        relative = Path(name)
        path = root / relative
        if any((root / parent).is_symlink() for parent in (relative, *relative.parents)):
            continue
        if not path.is_file():
            continue
        repository_relative = path.relative_to(repository_root).as_posix()
        if TICKET_REFERENCE.search(relative.as_posix()) and repository_relative != IMMUTABLE_MIGRATION_PATH:
            findings.append(PolicyFinding(relative, 1, "source-reference-path", "[REDACTED] matching path"))
        if path.name == ".env" or (path.name.startswith(".env.") and path.name not in ENVIRONMENT_EXAMPLE_NAMES):
            findings.append(
                PolicyFinding(relative, 1, "environment-file", "[REDACTED] environment contents")
            )
            continue
        if DATABASE_EXPORT.search(path.name):
            findings.append(
                PolicyFinding(relative, 1, "database-dump", "[REDACTED] database contents")
            )
            continue
        if (
            path.suffix.lower() not in TEXT_EXTENSIONS
            and path.name not in TEXT_NAMES
            and path.name not in ENVIRONMENT_EXAMPLE_NAMES
        ):
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            rules = []
            is_allowlisted_notice = (
                root == repository_root
                and relative.as_posix() in SOURCE_REFERENCE_ALLOWLIST
            )
            if not is_allowlisted_notice and (
                SOURCE_REFERENCE.search(line)
                or (TICKET_REFERENCE.search(EMBEDDED_IMAGE.sub("", line))
                    and not _is_immutable_revision_assignment(repository_relative, line))
            ):
                rules.append("source-reference")
            if PRIVATE_KEY.search(line):
                rules.append("private-key")
            if (
                SECRET_TOKEN.search(line)
                or _has_secret_assignment(line, path.name)
            ):
                rules.append("secret-value")
            findings.extend(
                PolicyFinding(relative, number, rule, "[REDACTED] matching line") for rule in rules
            )
    return findings


def _has_secret_assignment(line: str, filename: str) -> bool:
    match = SECRET_ASSIGNMENT.search(line)
    if match and not VARIABLE_REFERENCE.fullmatch(match.group("value")):
        return True
    if filename in ENVIRONMENT_EXAMPLE_NAMES:
        match = ENV_SECRET_ASSIGNMENT.search(line)
        if match:
            value = match.group("value") or match.group("bare")
            if not VARIABLE_REFERENCE.fullmatch(value):
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    try:
        findings = scan_public_copy(args.root)
    except (OSError, subprocess.CalledProcessError):
        parser.exit(1, "Public copy check could not read the tracked repository.\n")
    for finding in findings:
        print(f"{finding.file}:{finding.line}: {finding.rule}: {finding.excerpt}")
    if not findings:
        print("Public copy check passed.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
