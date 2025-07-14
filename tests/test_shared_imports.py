"""Ensure top-level package & sub-modules import correctly."""
import importlib


def test_import_root():
    assert importlib.import_module("layered_agent_full")


def test_import_protocol():
    proto = importlib.import_module("layered_agent_full.shared.protocol")
    assert hasattr(proto, "ChatMessage")


def test_make_skill_schema():
    from layered_agent_full.shared.protocol import make_skill_schema
    schema = make_skill_schema({
        "ping": {"name": "ping", "description": "icmp", "parameters": {"type": "object"}}
    })
    assert schema[0]["name"] == "ping"
