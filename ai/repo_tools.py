"""Read-only repository access tools for the AI (Tier B grounding).

The knowledge and agentic paths can read the project's own documentation and
code on demand via three bounded, allowlisted, read-only tools:

* ``read_file(path, start_line, end_line)`` - numbered lines from one file.
* ``search_code(pattern, path_prefix)`` - regex matches as ``path:line: text``.
* ``list_dir(path)`` - immediate entries of a directory.

Unlike Tier C (:mod:`ai.doc_retriever`), which pre-copies documentation chunks
into a ChromaDB index, these tools read the *live* files at call time: always
current, exact (``path:line``), and with no stored copy.

Full design, safety envelope, and rollout: ``docs/ai-code-access.md``.

Safety properties enforced here
-------------------------------

* **Allowlist roots** - only paths resolving inside the configured roots
  (``docs/``, ``backend/src/``, ``ai/``, ``frontend/src/``) are readable. Paths
  are resolved with :func:`os.path.realpath`, so ``..`` traversal, absolute
  paths, and **symlink escapes** are all rejected.
* **Secret denylist** - ``.env``/``*.key``/``*.pem`` and similar names are
  refused even inside a root.
* **Bounds** - line/hit/entry/byte caps with explicit truncation markers, and a
  per-run tool-call/byte budget (enforced by the agent loop).
* **Read-only** - nothing is ever opened for writing or executed.
* **Opt-in** - disabled by default (``code_access.enabled`` / ``AI_CODE_ACCESS``);
  when disabled the tools refuse and callers should not offer them.
"""

from __future__ import annotations

import contextvars
import fnmatch
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (overridden by ai/config.yaml `code_access:` and the env flag)
# ---------------------------------------------------------------------------

DEFAULT_ROOTS: Tuple[str, ...] = (
    "docs/",
    "backend/src/",
    "ai/",
    "frontend/src/",
)

DEFAULT_DENY: Tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "*credentials*",
    "*secret*",
)

DEFAULT_MAX_READ_LINES = 400
DEFAULT_MAX_HITS = 20
DEFAULT_MAX_ENTRIES = 200
DEFAULT_MAX_BYTES_PER_CALL = 65_536
DEFAULT_MAX_TOOL_CALLS = 6
DEFAULT_MAX_TOOL_BYTES = 262_144
DEFAULT_MAX_FILE_BYTES = 2_000_000

# Directories never descended into by ``search_code`` (noise, dependencies,
# build output, VCS metadata).
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "site",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".idea",
        ".vscode",
    }
)

_DISABLED_MSG = (
    "Repository access is disabled. Enable `code_access.enabled` in "
    "ai/config.yaml (or set AI_CODE_ACCESS=1) to use these tools."
)
_DENIED_MSG = (
    "Access denied: that path is outside the allowed repository roots "
    "(docs/, backend/src/, ai/, frontend/src/)."
)

_TRUTHY = frozenset({"1", "true", "yes", "on", "enabled"})
_FALSY = frozenset({"0", "false", "no", "off", "disabled"})


def _repo_root() -> str:
    """Return the repository root (the parent of the ``ai`` package)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _as_bool(raw: Any) -> Optional[bool]:
    """Coerce a config/env value to a bool, or ``None`` if unrecognised."""
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return None


def _cap_text(text: str, limit: int) -> Tuple[str, bool]:
    """Cap ``text`` to ``limit`` bytes-ish (chars), at a line boundary."""
    if limit <= 0 or len(text) <= limit:
        return text, False
    cut = text.rfind("\n", 0, limit)
    if cut <= 0:
        cut = limit
    return text[:cut].rstrip(), True


# ---------------------------------------------------------------------------
# Per-run configuration (ContextVar override + lazily built default)
# ---------------------------------------------------------------------------

_access_override: contextvars.ContextVar[Optional["RepoAccess"]] = (
    contextvars.ContextVar("repo_access_override", default=None)
)
_default_access: Optional["RepoAccess"] = None


def set_repo_access(access: Optional["RepoAccess"]) -> contextvars.Token:
    """Bind a :class:`RepoAccess` for the current context; returns a token."""
    return _access_override.set(access)


def reset_repo_access(token: contextvars.Token) -> None:
    """Restore the previous access policy using a token from ``set_...``."""
    _access_override.reset(token)


def get_repo_access() -> "RepoAccess":
    """Return the active :class:`RepoAccess` (context override, else default)."""
    override = _access_override.get()
    if override is not None:
        return override
    global _default_access
    if _default_access is None:
        _default_access = RepoAccess(root_path=_repo_root())
    return _default_access


def code_access_enabled() -> bool:
    """Return whether Tier B repository access is enabled."""
    return get_repo_access().enabled


# ---------------------------------------------------------------------------
# Per-run source sink (records which files a run actually read)
# ---------------------------------------------------------------------------

_source_sink: contextvars.ContextVar[Optional[List[str]]] = contextvars.ContextVar(
    "repo_source_sink", default=None
)


def set_repo_source_sink(sink: Optional[List[str]]) -> contextvars.Token:
    """Bind a list to collect the paths a run reads; returns a token."""
    return _source_sink.set(sink)


def reset_repo_source_sink(token: contextvars.Token) -> None:
    """Restore the previous source sink using a token from ``set_...``."""
    _source_sink.reset(token)


def get_repo_source_sink() -> Optional[List[str]]:
    """Return the source sink bound to the current context (or ``None``)."""
    return _source_sink.get()


def _record_sources(paths: Iterable[str]) -> None:
    """Append unique paths to the active source sink (no-op when unbound)."""
    sink = _source_sink.get()
    if sink is None:
        return
    for path in paths:
        if path and path not in sink:
            sink.append(path)


# ---------------------------------------------------------------------------
# The access policy
# ---------------------------------------------------------------------------


class RepoAccess:
    """Allowlisted, bounded, read-only access to a repository tree."""

    def __init__(
        self,
        root_path: str,
        config_path: Optional[str] = None,
        enabled: Optional[bool] = None,
        roots: Optional[Iterable[str]] = None,
        deny: Optional[Iterable[str]] = None,
        max_read_lines: Optional[int] = None,
        max_hits: Optional[int] = None,
        max_entries: Optional[int] = None,
        max_bytes_per_call: Optional[int] = None,
        max_tool_calls: Optional[int] = None,
        max_tool_bytes: Optional[int] = None,
        max_file_bytes: Optional[int] = None,
    ) -> None:
        """Initialise the policy.

        Args:
            root_path: Repository root that config paths are relative to.
            config_path: Path to ``config.yaml`` (defaults to ``ai/config.yaml``).
            enabled: Explicit enable override. When ``None`` the
                ``AI_CODE_ACCESS`` env var wins over the config ``enabled`` key;
                both absent means disabled.
            roots: Allowlist roots (defaults to the config key, else
                :data:`DEFAULT_ROOTS`).
            deny: Denylist globs (defaults to the config key, else
                :data:`DEFAULT_DENY`).
            max_read_lines: Cap on lines returned by one ``read_file``.
            max_hits: Cap on matches returned by one ``search_code``.
            max_entries: Cap on entries returned by one ``list_dir``.
            max_bytes_per_call: Byte cap on a single tool result.
            max_tool_calls: Per-run tool-call budget (read by the agent loop).
            max_tool_bytes: Per-run tool-result byte budget.
            max_file_bytes: Skip files larger than this.
        """
        self.root_path = os.path.abspath(root_path)
        if config_path is None:
            config_path = os.path.join(_repo_root(), "ai", "config.yaml")
        self._config_path = os.path.abspath(config_path)

        cfg: Dict[str, Any] = {}
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            cfg = loaded.get("code_access", {}) or {}
        except OSError as exc:  # pragma: no cover - config should exist
            logger.warning("Could not read code_access config %s: %s", config_path, exc)
        self.config = cfg

        self.enabled = self._resolve_enabled(enabled, cfg.get("enabled"))
        self.roots = list(
            roots if roots is not None else cfg.get("roots", DEFAULT_ROOTS)
        )
        self.deny = list(deny if deny is not None else cfg.get("deny", DEFAULT_DENY))

        self.max_read_lines = int(
            max_read_lines
            if max_read_lines is not None
            else cfg.get("max_read_lines", DEFAULT_MAX_READ_LINES)
        )
        self.max_hits = int(
            max_hits if max_hits is not None else cfg.get("max_hits", DEFAULT_MAX_HITS)
        )
        self.max_entries = int(
            max_entries
            if max_entries is not None
            else cfg.get("max_entries", DEFAULT_MAX_ENTRIES)
        )
        self.max_bytes_per_call = int(
            max_bytes_per_call
            if max_bytes_per_call is not None
            else cfg.get("max_bytes_per_call", DEFAULT_MAX_BYTES_PER_CALL)
        )
        self.max_tool_calls = int(
            max_tool_calls
            if max_tool_calls is not None
            else cfg.get("max_tool_calls", DEFAULT_MAX_TOOL_CALLS)
        )
        self.max_tool_bytes = int(
            max_tool_bytes
            if max_tool_bytes is not None
            else cfg.get("max_tool_bytes", DEFAULT_MAX_TOOL_BYTES)
        )
        self.max_file_bytes = int(
            max_file_bytes
            if max_file_bytes is not None
            else cfg.get("max_file_bytes", DEFAULT_MAX_FILE_BYTES)
        )

        # Pre-resolve the allowlist roots to real paths for containment checks.
        self._root_real: List[str] = [
            os.path.realpath(os.path.join(self.root_path, str(root).rstrip("/")))
            for root in self.roots
        ]

    # -- policy helpers ----------------------------------------------------

    @staticmethod
    def _resolve_enabled(explicit: Optional[bool], cfg_value: Any) -> bool:
        """Resolve the enabled flag: explicit > ``AI_CODE_ACCESS`` > config."""
        if explicit is not None:
            return explicit
        env = _as_bool(os.environ.get("AI_CODE_ACCESS"))
        if env is not None:
            return env
        cfg = _as_bool(cfg_value)
        return bool(cfg) if cfg is not None else False

    def _within_roots(self, real_path: str) -> bool:
        return any(
            real_path == root or real_path.startswith(root + os.sep)
            for root in self._root_real
        )

    def _is_denied(self, rel_path: str) -> bool:
        base = os.path.basename(rel_path).lower()
        rel = rel_path.replace(os.sep, "/").lower()
        for pattern in self.deny:
            pat = str(pattern).lower()
            if fnmatch.fnmatch(base, pat) or fnmatch.fnmatch(rel, pat):
                return True
        return False

    def resolve(self, path: str) -> Optional[str]:
        """Return the real absolute path if readable, else ``None``."""
        if not path or not isinstance(path, str):
            return None
        candidate = path.strip()
        if not candidate or os.path.isabs(candidate):
            return None
        real = os.path.realpath(os.path.join(self.root_path, candidate))
        if not self._within_roots(real):
            return None
        rel = os.path.relpath(real, self.root_path)
        if self._is_denied(rel):
            return None
        return real

    def _rel(self, real_path: str) -> str:
        return os.path.relpath(real_path, self.root_path).replace(os.sep, "/")

    # -- operations --------------------------------------------------------

    def read_file(self, path: str, start_line: int = 1, end_line: int = 0) -> str:
        """Return numbered lines from one allowlisted file."""
        if not self.enabled:
            return _DISABLED_MSG
        real = self.resolve(path)
        if real is None:
            return f"{_DENIED_MSG} (path={path!r})"
        if not os.path.isfile(real):
            return f"Not a file: {path!r}."
        try:
            if os.path.getsize(real) > self.max_file_bytes:
                return (
                    f"File too large to read in full: {path!r} "
                    f"({os.path.getsize(real)} bytes)."
                )
            with open(real, "r", encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            return f"Could not read {path!r}: {exc}"

        total = len(lines)
        start = max(int(start_line or 1), 1)
        requested_end = int(end_line or 0)
        auto_end = requested_end <= 0
        end = requested_end if requested_end > 0 else start + self.max_read_lines - 1
        capped_by_max = end > start + self.max_read_lines - 1
        end = min(end, start + self.max_read_lines - 1, total)
        if start > total:
            return f"{self._rel(real)} has only {total} lines."

        rel = self._rel(real)
        selected = lines[start - 1 : end]
        header = f"{rel} (lines {start}-{end} of {total})"
        body = "\n".join(
            f"{start + offset}: {line}" for offset, line in enumerate(selected)
        )
        text, byte_capped = _cap_text(f"{header}\n{body}", self.max_bytes_per_call)
        notes: List[str] = []
        # Only flag truncation when the range was capped for the model (a
        # defaulted end or a hit against max_read_lines) -- an explicit, smaller
        # window the model asked for is not a truncation.
        if end < total and (auto_end or capped_by_max):
            notes.append(f"{total - end} more lines")
        if byte_capped:
            notes.append("byte cap")
        if notes:
            text += f"\n... (truncated: {', '.join(notes)})"
        _record_sources([rel])
        return text

    def search_code(self, pattern: str, path_prefix: str = "") -> str:
        """Return ``path:line: text`` matches for a regex across the roots."""
        if not self.enabled:
            return _DISABLED_MSG
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return f"Invalid pattern {pattern!r}: {exc}"

        roots = self._search_roots(path_prefix)
        if roots is None:
            return f"{_DENIED_MSG} (path_prefix={path_prefix!r})"
        if not roots:
            return "No searchable directories in the allowlist."

        hits: List[str] = []
        matched_sources: List[str] = []
        truncated = False
        for base in roots:
            for file_path in self._iter_search_files(base):
                try:
                    if os.path.getsize(file_path) > self.max_file_bytes:
                        continue
                    with open(file_path, "r", encoding="utf-8") as handle:
                        file_lines = handle.read().splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                rel = self._rel(os.path.realpath(file_path))
                for lineno, line in enumerate(file_lines, 1):
                    if regex.search(line):
                        hits.append(f"{rel}:{lineno}: {line.strip()}")
                        if rel not in matched_sources:
                            matched_sources.append(rel)
                        if len(hits) >= self.max_hits:
                            truncated = True
                            break
                if truncated:
                    break
            if truncated:
                break

        if not hits:
            return f"No matches for {pattern!r}."
        text, byte_capped = _cap_text("\n".join(hits), self.max_bytes_per_call)
        if truncated:
            text += (
                f"\n... (showing first {len(hits)} matches; refine the pattern "
                "or path_prefix)"
            )
        if byte_capped:
            text += "\n... (truncated: byte cap)"
        _record_sources(matched_sources)
        return text

    def list_dir(self, path: str) -> str:
        """Return the immediate entries of one allowlisted directory."""
        if not self.enabled:
            return _DISABLED_MSG
        if not path or not str(path).strip():
            return "list_dir requires a path (e.g. 'docs' or 'backend/src')."
        real = self.resolve(path)
        if real is None:
            return f"{_DENIED_MSG} (path={path!r})"
        if not os.path.isdir(real):
            return f"Not a directory: {path!r}."
        try:
            names = sorted(os.listdir(real))
        except OSError as exc:
            return f"Could not list {path!r}: {exc}"

        entries: List[str] = []
        for name in names:
            if self._is_denied(name):
                continue
            full = os.path.join(real, name)
            entries.append(f"{name}/" if os.path.isdir(full) else name)

        rel = self._rel(real)
        shown = entries[: self.max_entries]
        text, byte_capped = _cap_text(
            f"{rel}/\n" + "\n".join(shown), self.max_bytes_per_call
        )
        if len(entries) > len(shown):
            text += f"\n... ({len(entries) - len(shown)} more entries)"
        if byte_capped:
            text += "\n... (truncated: byte cap)"
        return text

    # -- internals ---------------------------------------------------------

    def _search_roots(self, path_prefix: str) -> Optional[List[str]]:
        """Resolve a search scope: ``None`` if denied, else a list of dirs."""
        if not path_prefix or not str(path_prefix).strip():
            return [root for root in self._root_real if os.path.isdir(root)]
        real = self.resolve(path_prefix)
        if real is None:
            return None
        return [real]

    def _iter_search_files(self, base: str) -> Iterable[str]:
        """Yield readable files under ``base``, skipping noise and escapes."""
        if os.path.isfile(base):
            if not self._is_denied(os.path.basename(base)):
                yield base
            return
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in _SKIP_DIRS and not self._is_denied(name)
            ]
            for name in sorted(filenames):
                if self._is_denied(name):
                    continue
                full = os.path.join(dirpath, name)
                if self._within_roots(os.path.realpath(full)):
                    yield full


# ---------------------------------------------------------------------------
# Tool functions (schema-friendly signatures for the Ollama SDK)
# ---------------------------------------------------------------------------


def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
    """Read a repository file (documentation or source), with numbered lines.

    Use this to quote exact code or documentation. Paths are repo-relative
    (e.g. 'backend/src/homepot/models.py'); only the allowlisted trees are
    readable. Cite what you read as 'path:line'.

    Args:
        path: Repo-relative path to the file to read.
        start_line: First line to return (1-based; default 1).
        end_line: Last line to return (inclusive). 0 means "up to the cap".

    Returns:
        The file's numbered lines (capped, with a truncation marker), or an
        explanatory message when the path is unavailable or denied.
    """
    return get_repo_access().read_file(path, start_line, end_line)


def search_code(pattern: str, path_prefix: str = "") -> str:
    """Search the repository for a regular expression, returning matches.

    Use this to locate where something is defined or used. Results are
    'path:line: text'. Searches the allowlisted trees only.

    Args:
        pattern: A Python regular expression to search for (case-sensitive).
        path_prefix: Optional repo-relative file or directory to narrow the
            search (e.g. 'ai' or 'backend/src/homepot/models.py').

    Returns:
        Matching lines with their file and line number (capped), or a message
        when there are no matches or the scope is denied.
    """
    return get_repo_access().search_code(pattern, path_prefix)


def list_dir(path: str) -> str:
    """List the immediate entries of a repository directory.

    Use this to discover what files exist in an allowlisted tree before
    reading them.

    Args:
        path: Repo-relative directory (e.g. 'docs' or 'backend/src').

    Returns:
        The directory's immediate entries (sub-directories end with '/'),
        capped, or a message when the path is unavailable or denied.
    """
    return get_repo_access().list_dir(path)


# Map of tool name -> (function, is_async); mirrors ai/tools.TOOL_REGISTRY so
# the agent loop can execute these alongside the device tools.
REPO_TOOL_REGISTRY: Dict[str, Tuple[Any, bool]] = {
    "read_file": (read_file, False),
    "search_code": (search_code, False),
    "list_dir": (list_dir, False),
}

# Tool functions list for the Ollama SDK (auto-generates JSON schema).
REPO_TOOL_FUNCTIONS = [read_file, search_code, list_dir]
