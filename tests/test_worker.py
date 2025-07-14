import sys
from pathlib import Path
c6btom-codex/run-all-code-from-the-repo
=======
w55z61-codex/run-all-code-from-the-repo
main
from unittest import mock

# ensure package root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Provide stub modules to satisfy imports when dependencies are missing
sys.modules.setdefault('requests', mock.MagicMock())

def manual_discover():
    import importlib.util, inspect
    skills_dir = ROOT / 'layered_agent_full' / 'worker' / 'skills'
    sk = {}
    for f in skills_dir.glob('*.py'):
        if f.stem == '__init__':
            continue
        name = f"layered_agent_full.worker.skills.{f.stem}"
        spec = importlib.util.spec_from_file_location(name, f)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = 'layered_agent_full.worker.skills'
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if getattr(fn, '_is_skill', False):
                sk[name] = fn
    return sk


def test_discover_finds_skills():
    skills = manual_discover()
    assert 'run_shell' in skills
    assert 'capture_image' in skills
    assert 'record_audio' in skills

def test_sensor_fallback_when_modules_missing():
    from importlib import reload
    with mock.patch.dict(sys.modules, {'cv2': None}):
        from layered_agent_full.worker.skills import sensor
        reload(sensor)
        res = sensor.capture_image()
        assert 'error' in res
    with mock.patch.dict(sys.modules, {'sounddevice': None, 'numpy': None}):
        from layered_agent_full.worker.skills import sensor as sensor2
        reload(sensor2)
        res = sensor2.record_audio()
        assert 'error' in res
c6btom-codex/run-all-code-from-the-repo
=======
=======
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.worker.skills.core import run_shell


def load_worker():
    path = Path(__file__).resolve().parents[1] / 'layered_agent_full' / 'worker' / 'worker.py'
    source = path.read_text()
    pre = source.split('# main')[0]
    mod = types.ModuleType('worker_partial')
    mod.__dict__['__file__'] = str(path)
    exec(pre, mod.__dict__)
    return mod


def test_discover_via_module():
    worker = load_worker()
    skills = worker.discover()
    assert 'run_shell' in skills
    assert skills['run_shell'].__name__ == run_shell.__name__
main
main
