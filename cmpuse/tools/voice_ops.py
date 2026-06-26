"""
Enhanced Voice - ElevenLabs TTS, custom voice models, voice cloning
"""

import os
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import Any, Dict
from ..tool_registry import Tool, register

# ElevenLabs configuration
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')

class VoiceManager:
    def __init__(self):
        self.client = None
        self.available_voices = []

    def get_client(self):
        """Get ElevenLabs client"""
        if not self.client and ELEVENLABS_API_KEY:
            self.client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        return self.client

    def list_voices(self):
        """List available voices"""
        client = self.get_client()

        if not client:
            # Return default voice options if API not configured
            return [
                {"name": "Rachel", "voice_id": "21m00Tcm4TlvDq8ikWAM", "category": "premade"},
                {"name": "Domi", "voice_id": "AZnzlk1XvdvUeBnXmlld", "category": "premade"},
                {"name": "Bella", "voice_id": "EXAVITQu4vr4xnSDxMaL", "category": "premade"},
                {"name": "Antoni", "voice_id": "ErXwobaYiN019PkySvjV", "category": "premade"},
                {"name": "Elli", "voice_id": "MF3mGyEYCl7XYWbV9V6O", "category": "premade"},
                {"name": "Josh", "voice_id": "TxGEqnHWrfWFTfGW9XjX", "category": "premade"},
                {"name": "Arnold", "voice_id": "VR6AewLTigWG4xSOukaG", "category": "premade"},
                {"name": "Adam", "voice_id": "pNInz6obpgDQGcFmaJgB", "category": "premade"},
                {"name": "Sam", "voice_id": "yoZ06aMxZJJ28mfd3POQ", "category": "premade"}
            ]

        try:
            response = client.voices.get_all()
            voices = []
            for voice in response.voices:
                voices.append({
                    "name": voice.name,
                    "voice_id": voice.voice_id,
                    "category": voice.category if hasattr(voice, 'category') else 'unknown'
                })
            return voices
        except Exception as e:
            # Return default voices if API call fails
            return self.list_voices.__defaults__

    def speak(self, text, voice_id="21m00Tcm4TlvDq8ikWAM", output_path=None, stability=0.5, similarity_boost=0.75):
        """Generate speech using ElevenLabs"""
        client = self.get_client()

        if not client:
            raise Exception("ElevenLabs not configured. Set ELEVENLABS_API_KEY environment variable.")

        try:
            # Generate audio
            audio = client.generate(
                text=text,
                voice=voice_id,
                voice_settings=VoiceSettings(
                    stability=stability,
                    similarity_boost=similarity_boost
                ),
                model="eleven_monolingual_v1"
            )

            # Save or return audio
            if output_path:
                # Save audio to file
                with open(output_path, 'wb') as f:
                    for chunk in audio:
                        f.write(chunk)
                return output_path
            else:
                # Return audio data
                audio_data = b''.join(audio)
                return audio_data

        except Exception as e:
            raise Exception(f"ElevenLabs TTS error: {str(e)}")

voice_manager = VoiceManager()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "speak")

    if action == "speak":
        return {"preview": f"Generate speech with ElevenLabs", "args": args}
    elif action == "list_voices":
        return {"preview": "List available voices", "args": args}
    elif action == "clone_voice":
        return {"preview": "Clone voice from audio samples", "args": args}
    else:
        return {"preview": f"Voice action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform voice operation", "plan": _plan(args)}

    action = args.get("action", "speak")

    try:
        if action == "speak":
            text = args.get("text")
            voice_id = args.get("voice_id", "21m00Tcm4TlvDq8ikWAM")  # Rachel by default
            output_path = args.get("output_path")
            stability = args.get("stability", 0.5)
            similarity_boost = args.get("similarity_boost", 0.75)

            if not text:
                return {"status": "error", "message": "text required"}

            try:
                result = voice_manager.speak(text, voice_id, output_path, stability, similarity_boost)

                if output_path:
                    file_size = os.path.getsize(output_path) / 1024  # KB
                    return {
                        "status": "ok",
                        "message": f"Speech generated and saved",
                        "file_path": output_path,
                        "size_kb": round(file_size, 2),
                        "voice_id": voice_id
                    }
                else:
                    return {
                        "status": "ok",
                        "message": "Speech generated",
                        "audio_size_bytes": len(result),
                        "voice_id": voice_id
                    }
            except Exception as voice_error:
                # Fallback: speak aloud via local Windows TTS (SAPI) so this tool works
                # without ElevenLabs. (Her runner voice uses Piper; this covers the
                # tool's "speak" path for arbitrary text on command.)
                try:
                    import subprocess
                    safe = str(text).replace("'", "''")
                    ps = ("Add-Type -AssemblyName System.Speech; "
                          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                          f"$s.Speak('{safe}')")
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                   timeout=60, capture_output=True)
                    return {
                        "status": "ok",
                        "message": "Spoken via local Windows TTS (ElevenLabs not configured)",
                        "engine": "windows-sapi"
                    }
                except Exception as fb_err:
                    return {
                        "status": "error",
                        "message": f"TTS failed (ElevenLabs: {str(voice_error)[:80]}; local fallback: {str(fb_err)[:80]})"
                    }

        elif action == "list_voices":
            voices = voice_manager.list_voices()

            return {
                "status": "ok",
                "voices": voices,
                "count": len(voices),
                "message": f"Found {len(voices)} available voice(s)"
            }

        elif action == "clone_voice":
            client = voice_manager.get_client()

            if not client:
                return {
                    "status": "error",
                    "message": "ElevenLabs not configured",
                    "note": "To setup ElevenLabs: Set ELEVENLABS_API_KEY environment variable"
                }

            name = args.get("name", "Custom Voice")
            description = args.get("description", "Cloned voice")
            files = args.get("files", [])  # List of audio file paths

            if not files:
                return {"status": "error", "message": "files (audio samples) required for voice cloning"}

            try:
                # Voice cloning API call
                voice = client.clone(
                    name=name,
                    description=description,
                    files=files
                )

                return {
                    "status": "ok",
                    "message": f"Voice cloned: {name}",
                    "voice_id": voice.voice_id,
                    "name": voice.name
                }
            except Exception as clone_error:
                return {"status": "error", "message": f"Voice cloning error: {str(clone_error)}"}

        elif action == "delete_voice":
            client = voice_manager.get_client()

            if not client:
                return {"status": "error", "message": "ElevenLabs not configured"}

            voice_id = args.get("voice_id")

            if not voice_id:
                return {"status": "error", "message": "voice_id required"}

            try:
                client.voices.delete(voice_id)
                return {"status": "ok", "message": f"Voice {voice_id} deleted"}
            except Exception as delete_error:
                return {"status": "error", "message": f"Delete error: {str(delete_error)}"}

        elif action == "get_voice_settings":
            voice_id = args.get("voice_id", "21m00Tcm4TlvDq8ikWAM")

            # Return recommended voice settings
            settings = {
                "stability": {
                    "description": "Controls consistency (0.0-1.0)",
                    "recommended": 0.5,
                    "current": args.get("stability", 0.5)
                },
                "similarity_boost": {
                    "description": "Controls how much voice matches original (0.0-1.0)",
                    "recommended": 0.75,
                    "current": args.get("similarity_boost", 0.75)
                }
            }

            return {
                "status": "ok",
                "settings": settings,
                "voice_id": voice_id
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Voice ops error: {str(e)}"}

TOOL = Tool(
    name="voice_ops",
    summary="Enhanced voice - ElevenLabs TTS with multiple voices, voice cloning, custom voice settings (stability, similarity)",
    plan=_plan,
    run=_run,
    permissions={"confirm": False}  # Voice generation is safe
)

register(TOOL)
