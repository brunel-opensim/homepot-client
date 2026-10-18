"""Tests for read-only repository access (ai/repo_tools.py, Tier B).

These exercise the real allowlist/traversal/denylist/cap enforcement against a
throwaway repository tree, plus the opt-in flag resolution. No model or network
is involved.

See docs/ai-code-access.md for the design.
"""

import os
import sys

import pytest
import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai import repo_tools  # noqa: E402
from ai.repo_tools import (  # noqa: E402
    REPO_TOOL_FUNCTIONS,
    REPO_TOOL_REGISTRY,
    RepoAccess,
    reset_repo_access,
    reset_repo_source_sink,
    set_repo_access,
    set_repo_source_sink,
)


@pytest.fixture(autouse=True)
def _clean_repo_access(monkeypatch):
    """Isolate the ContextVar override and env flag between tests."""
    monkeypatch.delenv("AI_CODE_ACCESS", raising=False)
    token = set_repo_access(None)
    yield
    reset_repo_access(token)


def make_access(tmp_path, enabled=True, **cfg_overrides):
    """Build a RepoAccess over a temp repository + temp config."""
    root = tmp_path / "repo"
    for sub in ("docs", "backend/src", "ai", "frontend/src"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "docs" / "guide.md").write_text(
        "# Guide\n\nLine two.\nLine three.\n", encoding="utf-8"
    )
    (root / "backend" / "src" / "app.py").write_text(
        "def main():\n    return 'needle'\n", encoding="utf-8"
    )
    (root / "ai" / "core.py").write_text("NEEDLE_ONE = 1\n", encoding="utf-8")

    cfg = {"enabled": enabled}
    cfg.update(cfg_overrides)
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"code_access": cfg}), encoding="utf-8")
    return RepoAccess(root_path=str(root), config_path=str(config))


# ── allowlist / containment ──────────────────────────────────────────────────


def test_allowed_file_reads_with_numbered_lines(tmp_path):
    """A file inside an allowed root is readable with 1-based line numbers."""
    access = make_access(tmp_path)

    result = access.read_file("docs/guide.md")

    assert result.startswith("docs/guide.md (lines 1-4 of 4)")
    assert "1: # Guide" in result
    assert "2: " in result


def test_path_outside_roots_is_denied(tmp_path):
    """A path outside every allowlisted root is refused."""
    access = make_access(tmp_path)
    outside = tmp_path / "repo" / "README.md"
    outside.write_text("secret\n", encoding="utf-8")

    result = access.read_file("README.md")

    assert "Access denied" in result


def test_traversal_is_denied(tmp_path):
    """`..` traversal out of the roots is refused."""
    access = make_access(tmp_path)

    assert access.resolve("../config.yaml") is None
    assert "Access denied" in access.read_file("docs/../../etc/hosts")


def test_absolute_path_is_denied(tmp_path):
    """An absolute path is refused even if it points inside a root."""
    access = make_access(tmp_path)

    assert access.resolve("/etc/hosts") is None
    assert access.resolve(os.path.join(access.root_path, "docs", "guide.md")) is None


def test_leading_dot_slash_is_accepted(tmp_path):
    """A `./`-prefixed repo-relative path is normalised and allowed."""
    access = make_access(tmp_path)

    assert access.resolve("./docs/guide.md") is not None


def test_symlink_escape_is_denied(tmp_path):
    """A symlink inside a root that points outside it is refused."""
    access = make_access(tmp_path)
    outside = tmp_path / "outside_secret.md"
    outside.write_text("top secret\n", encoding="utf-8")
    link = os.path.join(access.root_path, "docs", "leak.md")
    try:
        os.symlink(str(outside), link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    assert access.resolve("docs/leak.md") is None
    assert "Access denied" in access.read_file("docs/leak.md")


def test_denylisted_secret_is_refused(tmp_path):
    """Secret-like file names are refused even inside a root."""
    access = make_access(tmp_path)
    (tmp_path / "repo" / "docs" / ".env").write_text("TOKEN=abc\n", encoding="utf-8")
    (tmp_path / "repo" / "ai" / "server.key").write_text("PRIVATE\n", encoding="utf-8")

    assert access.resolve("docs/.env") is None
    assert access.resolve("ai/server.key") is None
    assert "Access denied" in access.read_file("docs/.env")


def test_denylisted_dir_is_not_searched(tmp_path):
    """Files under a denied directory name are skipped by search."""
    access = make_access(tmp_path)
    secrets = tmp_path / "repo" / "frontend" / "src" / "secrets"
    secrets.mkdir(parents=True, exist_ok=True)
    (secrets / "config.js").write_text("const needed = 'needle';\n", encoding="utf-8")

    result = access.search_code("needle", "frontend/src")

    assert "secrets" not in result


# ── read_file bounds ─────────────────────────────────────────────────────────


def test_read_file_line_range(tmp_path):
    """start_line/end_line select an inclusive window."""
    access = make_access(tmp_path)

    result = access.read_file("docs/guide.md", start_line=2, end_line=3)

    assert result.startswith("docs/guide.md (lines 2-3 of 4)")
    assert "2: " in result
    assert "3: Line two." in result
    assert "1: # Guide" not in result
    # An explicit, smaller window is not labelled as truncated.
    assert "truncated" not in result


def test_read_file_line_cap_truncates(tmp_path):
    """A whole-file read is capped with a marker naming the remainder."""
    access = make_access(tmp_path, max_read_lines=10)
    big = tmp_path / "repo" / "docs" / "big.md"
    big.write_text("\n".join(f"line {i}" for i in range(25)), encoding="utf-8")

    result = access.read_file("docs/big.md")

    assert "truncated" in result
    assert "15 more lines" in result


def test_read_file_byte_cap_truncates(tmp_path):
    """A tiny byte cap truncates the output with a marker."""
    access = make_access(tmp_path, max_bytes_per_call=20)

    result = access.read_file("docs/guide.md")

    assert "byte cap" in result


def test_read_file_missing_file(tmp_path):
    """A non-existent allowed path reports 'Not a file'."""
    access = make_access(tmp_path)

    assert "Not a file" in access.read_file("docs/nope.md")


def test_read_file_start_beyond_end(tmp_path):
    """A start_line past EOF reports the file's length."""
    access = make_access(tmp_path)

    assert "has only 4 lines" in access.read_file("docs/guide.md", start_line=99)


# ── search_code ──────────────────────────────────────────────────────────────


def test_search_code_returns_path_line(tmp_path):
    """Matches are reported as path:line: text."""
    access = make_access(tmp_path)

    result = access.search_code("needle")

    assert "backend/src/app.py:2: " in result
    assert "return 'needle'" in result


def test_search_code_prefix_scopes_search(tmp_path):
    """path_prefix restricts the search to a subtree."""
    access = make_access(tmp_path)

    result = access.search_code("NEEDLE_ONE", "ai")

    assert "ai/core.py:1:" in result
    assert "backend/src/app.py" not in result


def test_search_code_caps_hits(tmp_path):
    """Hits are capped with a refinement hint."""
    access = make_access(tmp_path, max_hits=2)
    (tmp_path / "repo" / "docs" / "many.md").write_text(
        "\n".join("hit" for _ in range(5)), encoding="utf-8"
    )

    result = access.search_code("hit")

    assert "showing first 2 matches" in result


def test_search_code_no_matches(tmp_path):
    """A pattern with no hits returns a clear message."""
    access = make_access(tmp_path)

    assert "No matches" in access.search_code("zzz_absent_zzz")


def test_search_code_invalid_regex(tmp_path):
    """An invalid regex is reported rather than raised."""
    access = make_access(tmp_path)

    assert "Invalid pattern" in access.search_code("[unclosed")


def test_search_code_denied_prefix(tmp_path):
    """A search scoped outside the roots is refused."""
    access = make_access(tmp_path)

    assert "Access denied" in access.search_code("needle", "../")


# ── list_dir ─────────────────────────────────────────────────────────────────


def test_list_dir_lists_entries(tmp_path):
    """Directories are marked with a trailing slash."""
    access = make_access(tmp_path)
    (tmp_path / "repo" / "docs" / "sub").mkdir(exist_ok=True)

    result = access.list_dir("docs")

    assert result.startswith("docs/")
    assert "guide.md" in result
    assert "sub/" in result


def test_list_dir_caps_entries(tmp_path):
    """The entry count is capped with a marker."""
    access = make_access(tmp_path, max_entries=2)
    for i in range(5):
        (tmp_path / "repo" / "ai" / f"f{i}.py").write_text("x\n", encoding="utf-8")

    result = access.list_dir("ai")

    assert "more entries" in result


def test_list_dir_denied(tmp_path):
    """Listing outside the roots is refused."""
    access = make_access(tmp_path)

    assert "Access denied" in access.list_dir("..")


def test_list_dir_requires_path(tmp_path):
    """An empty path is rejected with guidance."""
    access = make_access(tmp_path)

    assert "requires a path" in access.list_dir("")


# ── opt-in flag ──────────────────────────────────────────────────────────────


def test_disabled_policy_refuses_all_tools(tmp_path):
    """When disabled, every tool refuses and logs the reason."""
    access = make_access(tmp_path, enabled=False)

    assert "disabled" in access.read_file("docs/guide.md")
    assert "disabled" in access.search_code("needle")
    assert "disabled" in access.list_dir("docs")


def test_enabled_resolution_config_only(tmp_path):
    """With no env override, the config `enabled` key decides."""
    assert make_access(tmp_path, enabled=True).enabled is True
    assert make_access(tmp_path, enabled=False).enabled is False


def test_env_flag_overrides_config(tmp_path, monkeypatch):
    """AI_CODE_ACCESS wins over the config key."""
    monkeypatch.setenv("AI_CODE_ACCESS", "0")
    assert make_access(tmp_path, enabled=True).enabled is False

    monkeypatch.setenv("AI_CODE_ACCESS", "1")
    assert make_access(tmp_path, enabled=False).enabled is True


def test_explicit_flag_overrides_env(tmp_path, monkeypatch):
    """An explicit `enabled` argument beats both env and config."""
    monkeypatch.setenv("AI_CODE_ACCESS", "1")
    base = make_access(tmp_path, enabled=True)

    forced_off = RepoAccess(
        root_path=base.root_path, config_path=base._config_path, enabled=False
    )
    assert forced_off.enabled is False

    monkeypatch.setenv("AI_CODE_ACCESS", "0")
    forced_on = RepoAccess(
        root_path=base.root_path, config_path=base._config_path, enabled=True
    )
    assert forced_on.enabled is True


def test_code_access_defaults_disabled(tmp_path):
    """The shipped repository config disables code access by default."""
    access = RepoAccess(root_path=repo_tools._repo_root())
    assert access.enabled is False


# ── sourcing + registry ──────────────────────────────────────────────────────


def test_source_sink_records_reads_and_matches(tmp_path):
    """read_file and search_code record the files they touch."""
    access = make_access(tmp_path)
    sink = []
    token = set_repo_source_sink(sink)
    try:
        access.read_file("docs/guide.md")
        access.search_code("needle")
    finally:
        reset_repo_source_sink(token)

    assert "docs/guide.md" in sink
    assert "backend/src/app.py" in sink


def test_source_sink_is_noop_when_unbound(tmp_path):
    """Recording without a sink does not raise."""
    access = make_access(tmp_path)

    assert access.read_file("docs/guide.md")  # no sink bound


def test_tool_functions_delegate_to_active_policy(tmp_path):
    """The schema-friendly tool functions use the active RepoAccess."""
    access = make_access(tmp_path)
    token = set_repo_access(access)
    try:
        assert "docs/guide.md" in repo_tools.read_file("docs/guide.md")
        assert "guide.md" in repo_tools.list_dir("docs")
        assert "backend/src/app.py:2:" in repo_tools.search_code("needle")
    finally:
        reset_repo_access(token)


def test_registry_contents():
    """The registry exposes exactly the three read-only tools."""
    assert set(REPO_TOOL_REGISTRY) == {"read_file", "search_code", "list_dir"}
    assert all(is_async is False for _, is_async in REPO_TOOL_REGISTRY.values())
    assert [fn.__name__ for fn in REPO_TOOL_FUNCTIONS] == [
        "read_file",
        "search_code",
        "list_dir",
    ]
