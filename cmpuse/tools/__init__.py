from .boot_repair import TOOL as boot_repair
from .json_ops import TOOL as json_ops
from .fs_ops import TOOL as fs_ops
from .net_ops import TOOL as net_ops
from .sys_ops import TOOL as sys_ops
from .layered_planner import TOOL as layered_planner
from .ps_exec import TOOL as ps_exec
from .open_item import TOOL as open_item
from .web_automation import TOOL as web_automation
from .memory_system import TOOL as memory_system
from .mouse_ops import TOOL as mouse_ops
from .key_ops import TOOL as key_ops
from .screen_ops import TOOL as screen_ops
from .vision_ops import TOOL as vision_ops
from .window_ops import TOOL as window_ops
from .audio_ops import TOOL as audio_ops
from .learning_db import TOOL as learning_db
# NEW JARVIS-LEVEL CAPABILITIES
from .iot_ops import TOOL as iot_ops
from .proactive_ops import TOOL as proactive_ops
from .remote_ops import TOOL as remote_ops
from .camera_ops import TOOL as camera_ops
from .security_ops import TOOL as security_ops
from .comm_ops import TOOL as comm_ops
from .calendar_ops import TOOL as calendar_ops
from .voice_ops import TOOL as voice_ops
from .analysis_ops import TOOL as analysis_ops
from .test_echo import TOOL as test_echo
from .computer_use import TOOL as computer_use
from .computer_use_control import TOOL as computer_use_control
from .self_awareness import TOOL as self_awareness
from .self_mod import TOOL as self_mod

# Import side-effects: ensure tools are registered when package is imported
__all__ = [
    "boot_repair",
    "json_ops",
    "fs_ops",
    "net_ops",
    "sys_ops",
    "layered_planner",
    "ps_exec",
    "open_item",
    "web_automation",
    "memory_system",
    "mouse_ops",
    "key_ops",
    "screen_ops",
    "vision_ops",
    "window_ops",
    "audio_ops",
    "learning_db",
    "iot_ops",
    "proactive_ops",
    "remote_ops",
    "camera_ops",
    "security_ops",
    "comm_ops",
    "calendar_ops",
    "voice_ops",
    "analysis_ops",
    "test_echo",
    "computer_use",
    "computer_use_control",
    "self_awareness",
    "self_mod",
]
