"""
IoT & Smart Home Control - Home Assistant, MQTT, smart devices
"""

from .._lazyimport import lazy_module
mqtt = lazy_module("paho.mqtt.client")   # deferred to first use
requests = lazy_module("requests")
import json
from typing import Any, Dict
from ..tool_registry import Tool, register

# Configuration (to be set by user)
HOME_ASSISTANT_URL = "http://homeassistant.local:8123"
HOME_ASSISTANT_TOKEN = ""  # Set via environment or config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

class IoTManager:
    def __init__(self):
        self.mqtt_client = None
        self.ha_headers = {
            "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
            "Content-Type": "application/json"
        }

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        if not self.mqtt_client:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
        return self.mqtt_client

    def home_assistant_call(self, endpoint, method="GET", data=None):
        """Call Home Assistant API"""
        url = f"{HOME_ASSISTANT_URL}/api/{endpoint}"
        if method == "GET":
            response = requests.get(url, headers=self.ha_headers)
        elif method == "POST":
            response = requests.post(url, headers=self.ha_headers, json=data)
        return response.json()

iot_manager = IoTManager()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "list_devices")
    device = args.get("device", "")

    if action == "list_devices":
        return {"preview": "List all smart home devices", "args": args}
    elif action == "turn_on":
        return {"preview": f"Turn on {device}", "args": args}
    elif action == "turn_off":
        return {"preview": f"Turn off {device}", "args": args}
    elif action == "set_brightness":
        return {"preview": f"Set {device} brightness to {args.get('brightness', 50)}%", "args": args}
    elif action == "set_temperature":
        return {"preview": f"Set thermostat to {args.get('temperature')}°", "args": args}
    elif action == "mqtt_publish":
        return {"preview": f"Publish MQTT message to {args.get('topic')}", "args": args}
    else:
        return {"preview": f"IoT action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform IoT operation", "plan": _plan(args)}

    action = args.get("action", "list_devices")

    try:
        # Home Assistant Actions
        if action == "list_devices":
            try:
                states = iot_manager.home_assistant_call("states")
                devices = []
                for state in states:
                    devices.append({
                        "entity_id": state["entity_id"],
                        "friendly_name": state["attributes"].get("friendly_name", "Unknown"),
                        "state": state["state"],
                        "type": state["entity_id"].split(".")[0]
                    })
                return {"status": "ok", "devices": devices, "count": len(devices)}
            except Exception as ha_error:
                # Fallback: return simulated device list
                return {
                    "status": "info",
                    "message": "Home Assistant not configured. Configure HOME_ASSISTANT_URL and TOKEN to connect.",
                    "devices": [],
                    "note": "To setup: Set environment variables or update iot_ops.py with your Home Assistant URL and long-lived access token"
                }

        elif action in ["turn_on", "turn_off"]:
            entity_id = args.get("entity_id") or args.get("device")
            if not entity_id:
                return {"status": "error", "message": "entity_id required"}

            service = "turn_on" if action == "turn_on" else "turn_off"
            domain = entity_id.split(".")[0]

            result = iot_manager.home_assistant_call(
                f"services/{domain}/{service}",
                method="POST",
                data={"entity_id": entity_id}
            )
            return {"status": "ok", "message": f"Device {entity_id} {service} success", "result": result}

        elif action == "set_brightness":
            entity_id = args.get("entity_id") or args.get("device")
            brightness = args.get("brightness", 50)  # 0-100

            result = iot_manager.home_assistant_call(
                "services/light/turn_on",
                method="POST",
                data={"entity_id": entity_id, "brightness_pct": brightness}
            )
            return {"status": "ok", "message": f"Set {entity_id} brightness to {brightness}%"}

        elif action == "set_temperature":
            entity_id = args.get("entity_id") or args.get("device")
            temperature = args.get("temperature")

            result = iot_manager.home_assistant_call(
                "services/climate/set_temperature",
                method="POST",
                data={"entity_id": entity_id, "temperature": temperature}
            )
            return {"status": "ok", "message": f"Set {entity_id} to {temperature}°"}

        # MQTT Actions
        elif action == "mqtt_publish":
            topic = args.get("topic")
            message = args.get("message")

            if not topic or not message:
                return {"status": "error", "message": "topic and message required"}

            client = iot_manager.connect_mqtt()
            client.publish(topic, json.dumps(message) if isinstance(message, dict) else message)
            return {"status": "ok", "message": f"Published to {topic}"}

        elif action == "mqtt_subscribe":
            topic = args.get("topic")
            timeout = args.get("timeout", 5)

            messages = []

            def on_message(client, userdata, msg):
                messages.append({
                    "topic": msg.topic,
                    "payload": msg.payload.decode(),
                    "qos": msg.qos
                })

            client = iot_manager.connect_mqtt()
            client.on_message = on_message
            client.subscribe(topic)

            import time
            time.sleep(timeout)

            return {"status": "ok", "messages": messages, "count": len(messages)}

        # Generic Device Control
        elif action == "get_state":
            entity_id = args.get("entity_id") or args.get("device")
            state = iot_manager.home_assistant_call(f"states/{entity_id}")
            return {"status": "ok", "state": state}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"IoT operation error: {str(e)}"}

TOOL = Tool(
    name="iot_ops",
    summary="IoT & Smart Home control - Home Assistant integration, MQTT messaging, smart device control (lights, thermostats, locks)",
    plan=_plan,
    run=_run,
    permissions={"confirm": True}  # Smart home control requires confirmation
)

register(TOOL)
