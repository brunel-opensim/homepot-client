"""Parity tests: the emulator's OS->capability/push heuristics == the backend's.

Before the refactor that introduced ``homepot.app.schemas.os_capabilities``,
``emulators/pos_engine.py`` maintained a copy of the backend's capability and
push-channel derivation. The two had already drifted (e.g. the emulator
omitted ``command_execution`` for Android/Windows and did not classify the
bare ``"mac"`` token). Now ``pos_engine`` imports the canonical module,
falling back to a PyInstaller-bundled copy when the backend is unavailable.

These tests pin the two halves together:

- the dev path (``homepot`` importable): the emulator must resolve to the very
  same functions the backend uses;
- the frozen path (backend unreachable): importing ``os_capabilities`` from
  the bundled layout must reproduce the backend's results for the same corpus.
"""

import subprocess  # noqa: S404  (only checks frozen-bundle parity)
import sys
from pathlib import Path

BACKEND_CANONICAL = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "homepot"
    / "app"
    / "schemas"
    / "os_capabilities.py"
)

EMULATORS_DIR = Path(__file__).resolve().parents[2] / "emulators"

# The emulator modules are not a package; tests import them straight from the
# checked-out ``emulators/`` dir (mirrors emulator_entry's sys.path setup).
sys.path.insert(0, str(EMULATORS_DIR))

from pos_engine import (  # noqa: E402,F401  (needs emulators dir on sys.path)
    derive_os_capabilities,
    derive_push_channel as emu_push_channel,
)

CORPUS = [
    "",
    "unknown-runtime",
    "windows",
    "Windows 11",
    "win32",
    "win64",
    "linux",
    "Linux 6.8.0 (Debian 12)",
    "ubuntu 22.04",
    "debian 12",
    "fedora 40",
    "centos 9",
    "raspberry pi OS",
    "macos",
    "mac",
    "macOS 14",
    "mac os",
    "darwin",
    "os x",
    "ios",
    "iOS 17",
    "ipados",
    "ipados 17",
    "iphone os",
    "ipad",
    "android",
    "Android 14",
]


def test_emulator_matches_backend_in_dev():
    """In the dev layout the emulator must use the backend's own functions."""
    from homepot.app.schemas.os_capabilities import (
        derive_capabilities,
        derive_push_channel,
    )

    assert derive_os_capabilities is derive_capabilities
    assert emu_push_channel is derive_push_channel
    for os_details in CORPUS:
        assert derive_os_capabilities(os_details) == derive_capabilities(os_details)
        assert emu_push_channel(os_details) == derive_push_channel(os_details)
    assert derive_os_capabilities(None) == derive_capabilities(None)
    assert emu_push_channel(None) == derive_push_channel(None)


def test_frozen_layout_reproduces_backend_behaviour():
    """With the backend package hidden, the bundled copy must match.

    The emulator spec copies ``os_capabilities.py`` into the emulators dir
    (``sys._MEIPASS/emulators``) and ``emulator_entry`` puts that dir on
    ``sys.path``. We reproduce the layout: a temp dir holds a copy of the
    canonical file (the "bundle"), ``pos_engine`` is imported from the real
    ``emulators/`` tree while ``homepot`` is blocked, so its fallback
    ``import os_capabilities`` branch fires.
    """
    script = f"""
import importlib.util
import sys
import tempfile
from pathlib import Path

emulators_dir = {str(EMULATORS_DIR)!r}
canonical = Path({str(BACKEND_CANONICAL)!r})

tmp = Path(tempfile.mkdtemp(prefix="emu-bundle-"))
(tmp / "os_capabilities.py").write_bytes(canonical.read_bytes())

# Build an importable spec for the canonical file under its real location so we
# can compare against it without going through the (blocked) homepot package.
canonical_spec = importlib.util.spec_from_file_location("_canonical", canonical)
canonical_mod = importlib.util.module_from_spec(canonical_spec)
canonical_spec.loader.exec_module(canonical_mod)

# Block the backend package exactly as in the frozen emulator.
import types
blocker = types.ModuleType("homepot")
blocker.__path__ = []
sys.modules["homepot"] = blocker

sys.path.insert(0, str(tmp))       # bundled os_capabilities copy
sys.path.insert(0, emulators_dir)  # pos_engine and wrappers

from pos_engine import (  # noqa: E402  (fallback branch fires here)
    derive_os_capabilities,
    derive_push_channel,
)

corpus = {CORPUS!r} + [None]
mismatches = []
for d in corpus:
    if derive_os_capabilities(d) != canonical_mod.derive_capabilities(d):
        mismatches.append(("capabilities", d))
    if derive_push_channel(d) != canonical_mod.derive_push_channel(d):
        mismatches.append(("push_channel", d))

if mismatches:
    print("MISMATCHES", mismatches)
    raise SystemExit(1)
print("OK")
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=EMULATORS_DIR,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    assert "OK" in result.stdout


def test_bundled_os_capabilities_is_the_canonical_file():
    """The exact file bundled by the emulator spec is the backend's module."""
    spec = (Path(__file__).resolve().parents[2] / "packaging" / "emulator.spec").resolve()
    text = spec.read_text(encoding="utf-8")
    assert "os_capabilities.py" in text
    assert '"emulators"' in text
    assert BACKEND_CANONICAL.exists()
