import sys
from pathlib import Path
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
