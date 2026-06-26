"""
Audio Operations Tool - System volume control + OpenAI native audio (TTS, transcription, realtime voice)
"""

import os
import base64
from pathlib import Path
from typing import Any, Dict

from ..tool_registry import Tool, register

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "get_volume")

    # System Volume Control
    if action == "get_volume":
        return {"preview": "Get current system volume", "args": args}
    elif action == "set_volume":
        volume = args.get("volume", 50)
        return {"preview": f"Set volume to {volume}%", "args": args}
    elif action == "mute":
        return {"preview": "Mute system audio", "args": args}
    elif action == "unmute":
        return {"preview": "Unmute system audio", "args": args}
    elif action == "increase":
        amount = args.get("amount", 10)
        return {"preview": f"Increase volume by {amount}%", "args": args}
    elif action == "decrease":
        amount = args.get("amount", 10)
        return {"preview": f"Decrease volume by {amount}%", "args": args}

    # OpenAI Audio - TTS
    elif action == "speak" or action == "tts":
        text = args.get("text", "")[:50]
        voice = args.get("voice", "sage")
        return {"preview": f"Speak with {voice} voice: '{text}...'", "args": args}

    # OpenAI Audio - Transcription
    elif action == "transcribe":
        audio_file = args.get("audio_file", "")
        return {"preview": f"Transcribe audio file: {audio_file}", "args": args}
    elif action == "transcribe_diarize":
        return {"preview": "Transcribe audio with speaker identification", "args": args}

    # OpenAI Audio - Audio-aware conversation
    elif action == "audio_conversation":
        prompt = args.get("prompt", "")[:50]
        return {"preview": f"Audio-aware conversation: '{prompt}...'", "args": args}

    # OpenAI Audio - Realtime API
    elif action == "realtime_info":
        return {"preview": "Get OpenAI Realtime Voice API information", "args": args}

    else:
        return {"preview": f"Audio action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform audio operation", "plan": _plan(args)}

    action = args.get("action", "get_volume")

    # ========================================================================
    # SYSTEM VOLUME CONTROL
    # ========================================================================
    if action in ["get_volume", "set_volume", "mute", "unmute", "increase", "decrease"]:
        return _system_volume_control(args, action)

    # ========================================================================
    # OPENAI AUDIO OPERATIONS
    # ========================================================================
    elif action in ["speak", "tts", "transcribe", "transcribe_diarize", "audio_conversation", "realtime_info"]:
        return _openai_audio(args, action)

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


def _system_volume_control(args: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Handle system volume control operations"""
    try:
        from pycaw.pycaw import AudioUtilities

        # Get default audio device (updated API)
        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume

        if action == "get_volume":
            current_volume = volume.GetMasterVolumeLevelScalar() * 100
            is_muted = volume.GetMute()

            return {
                "status": "ok",
                "message": f"Volume: {current_volume:.0f}%{' (muted)' if is_muted else ''}",
                "volume": round(current_volume),
                "muted": bool(is_muted)
            }

        elif action == "set_volume":
            target_volume = args.get("volume", 50)
            if not 0 <= target_volume <= 100:
                return {"status": "error", "message": "Volume must be between 0 and 100"}

            volume.SetMasterVolumeLevelScalar(target_volume / 100.0, None)
            return {"status": "ok", "message": f"Volume set to {target_volume}%", "volume": target_volume}

        elif action == "mute":
            volume.SetMute(1, None)
            return {"status": "ok", "message": "Audio muted", "muted": True}

        elif action == "unmute":
            volume.SetMute(0, None)
            current_volume = volume.GetMasterVolumeLevelScalar() * 100
            return {"status": "ok", "message": f"Audio unmuted (volume: {current_volume:.0f}%)", "muted": False}

        elif action == "increase":
            amount = args.get("amount", 10)
            current = volume.GetMasterVolumeLevelScalar() * 100
            new_volume = min(100, current + amount)
            volume.SetMasterVolumeLevelScalar(new_volume / 100.0, None)
            return {"status": "ok", "message": f"Volume increased to {new_volume:.0f}%", "volume": round(new_volume)}

        elif action == "decrease":
            amount = args.get("amount", 10)
            current = volume.GetMasterVolumeLevelScalar() * 100
            new_volume = max(0, current - amount)
            volume.SetMasterVolumeLevelScalar(new_volume / 100.0, None)
            return {"status": "ok", "message": f"Volume decreased to {new_volume:.0f}%", "volume": round(new_volume)}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Audio control error: {str(e)}"}


def _openai_audio(args: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Handle OpenAI native audio operations"""
    try:
        from openai import OpenAI
        from ..secrets import load_into_env

        load_into_env()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"status": "error", "message": "OpenAI API key not configured"}

        client = OpenAI(api_key=api_key)

        # ====================================================================
        # TEXT-TO-SPEECH (TTS)
        # ====================================================================
        if action == "speak" or action == "tts":
            text = args.get("text")
            if not text:
                return {"status": "error", "message": "text parameter required"}

            # Voice options: sage (new), coral (new), ash (new), nova, alloy, echo, fable, onyx, shimmer
            voice = args.get("voice", "sage")  # Sage is default voice for AVA
            model = args.get("model", "tts-1-hd")  # High definition TTS

            # Speed: 0.25 to 4.0 (default 1.0)
            speed = args.get("speed", 1.0)

            # Output format: mp3, opus, aac, flac, wav, pcm
            output_format = args.get("format", "mp3")

            # Generate speech
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
                response_format=output_format
            )

            # Save to file or play immediately
            output_file = args.get("output_file")

            if output_file:
                # Save to specified file
                response.stream_to_file(output_file)
                return {
                    "status": "ok",
                    "message": f"Speech saved to {output_file}",
                    "output_file": output_file,
                    "voice": voice,
                    "model": model
                }
            else:
                # Save to temp file and play
                audio_bytes = response.content

                temp_dir = Path.home() / ".cmpuse" / "temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_file = temp_dir / f"speech_{hash(text)}.{output_format}"

                with open(temp_file, "wb") as f:
                    f.write(audio_bytes)

                # Play the audio
                _play_audio(str(temp_file))

                return {
                    "status": "ok",
                    "message": f"Spoke {len(text)} characters with {voice} voice",
                    "text": text,
                    "voice": voice,
                    "model": model,
                    "audio_file": str(temp_file),
                    "audio_bytes": len(audio_bytes)
                }

        # ====================================================================
        # SPEECH-TO-TEXT (Transcription)
        # ====================================================================
        elif action == "transcribe":
            audio_file = args.get("audio_file")
            if not audio_file or not os.path.exists(audio_file):
                return {"status": "error", "message": "Valid audio_file required"}

            model = args.get("model", "whisper-1")  # or gpt-4o-transcribe for advanced features

            # Language (optional) - ISO-639-1 code (e.g., "en", "es")
            language = args.get("language")

            # Prompt for context (optional)
            prompt = args.get("prompt")

            # Response format: json, text, srt, verbose_json, vtt
            response_format = args.get("response_format", "json")

            # Temperature: 0-1 (default 0)
            temperature = args.get("temperature", 0)

            with open(audio_file, "rb") as audio:
                kwargs = {
                    "model": model,
                    "file": audio,
                    "response_format": response_format,
                    "temperature": temperature
                }

                if language:
                    kwargs["language"] = language
                if prompt:
                    kwargs["prompt"] = prompt

                transcript = client.audio.transcriptions.create(**kwargs)

            # Parse response based on format
            if response_format == "json" or response_format == "verbose_json":
                text = transcript.text
                return {
                    "status": "ok",
                    "message": f"Transcribed {len(text)} characters",
                    "text": text,
                    "model": model,
                    "language": language or "auto-detected"
                }
            else:
                return {
                    "status": "ok",
                    "message": "Transcription complete",
                    "transcript": str(transcript),
                    "model": model
                }

        # ====================================================================
        # SPEECH-TO-TEXT WITH DIARIZATION
        # ====================================================================
        elif action == "transcribe_diarize":
            audio_file = args.get("audio_file")
            if not audio_file or not os.path.exists(audio_file):
                return {"status": "error", "message": "Valid audio_file required"}

            model = "gpt-4o-transcribe-diarize"

            with open(audio_file, "rb") as audio:
                transcript = client.audio.transcriptions.create(
                    model=model,
                    file=audio,
                    response_format="verbose_json"
                )

            # Extract speaker segments
            segments = []
            if hasattr(transcript, 'segments'):
                for seg in transcript.segments:
                    segments.append({
                        "speaker": getattr(seg, 'speaker', 'Unknown'),
                        "text": seg.text,
                        "start": seg.start,
                        "end": seg.end
                    })

            return {
                "status": "ok",
                "message": f"Transcribed with {len(segments)} speaker segments",
                "text": transcript.text,
                "segments": segments,
                "model": model
            }

        # ====================================================================
        # AUDIO-AWARE CONVERSATION
        # ====================================================================
        elif action == "audio_conversation":
            prompt = args.get("prompt")
            if not prompt:
                return {"status": "error", "message": "prompt required"}

            audio_file = args.get("audio_file")  # Optional audio input
            model = args.get("model", "gpt-4o-audio-preview")

            messages = [{"role": "user", "content": []}]

            # Add text
            messages[0]["content"].append({"type": "text", "text": prompt})

            # Add audio if provided
            if audio_file and os.path.exists(audio_file):
                with open(audio_file, "rb") as f:
                    audio_data = base64.b64encode(f.read()).decode('utf-8')

                messages[0]["content"].append({
                    "type": "audio",
                    "audio": {
                        "data": audio_data,
                        "format": audio_file.split('.')[-1]
                    }
                })

            # Call audio-aware model
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )

            answer = response.choices[0].message.content

            return {
                "status": "ok",
                "message": "Audio-aware conversation complete",
                "response": answer,
                "model": model,
                "had_audio_input": bool(audio_file)
            }

        # ====================================================================
        # REALTIME VOICE API INFO
        # ====================================================================
        elif action == "realtime_info":
            return {
                "status": "info",
                "message": "OpenAI Realtime Voice API information",
                "note": "Realtime API requires WebSocket connection for bidirectional voice",
                "models": ["gpt-4o-realtime-preview", "gpt-realtime"],
                "features": [
                    "Low-latency voice-to-voice conversations",
                    "Streaming audio input/output",
                    "Function calling during voice chat",
                    "Automatic turn detection",
                    "Interruption handling",
                    "6 voice options (alloy, echo, fable, onyx, nova, shimmer)"
                ],
                "documentation": "https://platform.openai.com/docs/guides/realtime",
                "implementation": "Use WebSocket client to connect to wss://api.openai.com/v1/realtime"
            }

        else:
            return {"status": "error", "message": f"Unknown OpenAI audio action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"OpenAI audio error: {str(e)}"}


def _play_audio(audio_file: str) -> bool:
    """Play audio file using system default player"""
    try:
        import platform
        import subprocess

        system = platform.system()

        if system == "Windows":
            # Use Windows default audio player
            os.startfile(audio_file)
            return True
        elif system == "Darwin":  # macOS
            subprocess.run(["afplay", audio_file])
            return True
        elif system == "Linux":
            # Try common Linux audio players
            for player in ["paplay", "aplay", "mpg123", "ffplay"]:
                try:
                    subprocess.run([player, audio_file], timeout=1)
                    return True
                except:
                    continue

        return False
    except Exception:
        return False


TOOL = Tool(
    name="audio_ops",
    summary="Audio operations - System volume control + OpenAI native TTS (speak/tts), transcription (transcribe/transcribe_diarize), audio-aware conversations, realtime voice API",
    plan=_plan,
    run=_run,
    permissions={"confirm": False}  # Audio control is generally safe
)

register(TOOL)
