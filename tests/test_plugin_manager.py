import sys
from pathlib import Path
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.plugin_manager import PluginManager

# load refresh_skills from worker without executing main

def load_refresh():
    path = Path(__file__).resolve().parents[1] / 'layered_agent_full' / 'worker' / 'worker.py'
    source = path.read_text()
    pre = source.split('# main')[0]
    mod = types.ModuleType('worker_partial')
    mod.__dict__['__file__'] = str(path)
    exec(pre, mod.__dict__)
    return mod.refresh_skills, mod


def test_plugin_loading(tmp_path):
    plug_dir = tmp_path / 'plugins'
    plug_dir.mkdir()
    plugin_file = plug_dir / 'greet.py'
    plugin_file.write_text(
        "from layered_agent_full.worker.skills.core import skill\n\n" \
        "@skill\n" \
        "def greet(name: str):\n" \
        "    return f'Hello {name}'\n"
    )

    pm = PluginManager(plugin_dir=plug_dir)
    refresh_skills, mod = load_refresh()

    refresh_skills(pm)
    assert 'greet' in mod.skills
    assert callable(mod.skills['greet'])
