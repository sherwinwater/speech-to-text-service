import sys
import types

from tests.conftest import _StubVad, ensure_webrtc_stub


def test_ensure_webrtc_stub_installs_module(monkeypatch):
    """When webrtcvad is missing, ensure_webrtc_stub should register the stub module."""
    monkeypatch.delitem(sys.modules, "webrtcvad", raising=False)

    ensure_webrtc_stub()

    module = sys.modules.get("webrtcvad")
    assert module is not None
    vad_cls = getattr(module, "Vad")
    assert vad_cls.__module__ == "tests.conftest"
    assert vad_cls.__name__ == "_StubVad"
    instance = vad_cls(2)
    assert instance.aggressiveness == 2


def test_ensure_webrtc_stub_preserves_existing_module(monkeypatch):
    """Existing modules with a Vad attribute should not be overwritten."""
    class CustomVad:  # pragma: no cover - trivial definition
        pass

    module = types.ModuleType("webrtcvad")
    setattr(module, "Vad", CustomVad)
    monkeypatch.setitem(sys.modules, "webrtcvad", module)

    ensure_webrtc_stub()

    assert sys.modules["webrtcvad"].Vad is CustomVad
