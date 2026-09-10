"""Pin the frozen-bundle data layout so boot regressions stay caught.

The smoke-test failure this guards against: ``agent.spec`` bundled
``agent-config.json`` to ``_MEIPASS/homepot/agent/`` while
``load_agent_config()`` resolves ``Path(__file__).parent / "agent-config.json"``
— i.e. ``_MEIPASS/agent-config.json``. The frozen agent therefore crashed with
``FileNotFoundError`` at boot. (The CI smoke probe is the only path that runs
the frozen binary without ``$HOMEPOT_AGENT_CONFIG``; the Electron shell always
sets it, which is why the bug shipped for months undetected.)
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
AGENT_SPEC = ROOT / "packaging" / "agent.spec"
EMULATOR_SPEC = ROOT / "packaging" / "emulator.spec"


def test_agent_config_is_bundled_at_agent_bundle_root():
    """`agent-config.json` must land where ``load_agent_config()`` looks.

    The frozen agent resolves ``Path(__file__).parent`` to ``_MEIPASS``, so the
    datas dest must be the bundle root (``"."``). A subdir dest (e.g.
    ``"homepot/agent"``) silently relocates the file and crashes the binary at
    boot as soon as no ``$HOMEPOT_AGENT_CONFIG`` is provided.
    """
    text = AGENT_SPEC.read_text(encoding="utf-8")
    assert "agent-config.json" in text, "agent.spec must bundle agent-config.json"

    datas = re.findall(r"""agent-config\.json.*?,\s*"([^"]+)"\s*\)""", text)
    assert datas, "no PyInstaller datas tuple references agent-config.json"
    dest = datas[-1]
    assert dest == ".", (
        "agent-config.json must be bundled at the PyInstaller bundle root (dest "
        "'.'), got {dest!r} — load_agent_config() resolves "
        "Path(__file__).parent / 'agent-config.json' == _MEIPASS/agent-config.json"
    )


def test_emulator_spec_still_bundles_os_capabilities_as_datas():
    """Regression guard: the emulator bundle still carries the canonical module."""
    text = EMULATOR_SPEC.read_text(encoding="utf-8")
    assert "os_capabilities.py" in text
    assert '"emulators"' in text
