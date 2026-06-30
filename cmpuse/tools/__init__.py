# Resilient tool registry: a tool whose optional dependency is missing is skipped
# (logged) instead of crashing the entire cmpuse.tools import. This keeps the
# package importable on machines that don't have every tool's deps installed.
import importlib as _importlib

_TOOL_MODULES = [
    "boot_repair", "json_ops", "fs_ops", "net_ops", "sys_ops", "layered_planner",
    "ps_exec", "open_item", "web_automation", "memory_system", "mouse_ops",
    "key_ops", "screen_ops", "vision_ops", "window_ops", "audio_ops",
    "learning_db", "iot_ops", "proactive_ops", "remote_ops", "camera_ops",
    "security_ops", "comm_ops", "calendar_ops", "voice_ops", "analysis_ops",
    "test_echo", "computer_use", "computer_use_control", "self_awareness",
    "self_mod", "profile_ops", "app_control", "file_resolve", "self_diagnostics",
    "image_ops", "model3d_ops", "web_builder", "scene3d", "web_search",
]

__all__ = []
_g = globals()
_skipped = []
for _name in _TOOL_MODULES:
    try:
        _mod = _importlib.import_module("." + _name, __name__)
        _g[_name] = getattr(_mod, "TOOL", None)
        __all__.append(_name)
    except Exception as _e:  # missing optional dependency, etc.
        _g[_name] = None
        _skipped.append(_name)
        try:
            print(f"[cmpuse.tools] skipped {_name}: {type(_e).__name__}: {_e}")
        except Exception:
            pass

if _skipped:
    try:
        print(f"[cmpuse.tools] {len(__all__)} tools loaded, {len(_skipped)} skipped: {', '.join(_skipped)}")
    except Exception:
        pass
