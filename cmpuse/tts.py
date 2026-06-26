from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path


def speak(text: str, allow_shell: bool = False) -> bool:
    if not text:
        return False

    # PRIORITY 1: OpenAI TTS (best quality, most natural voice)
    if os.getenv("CMPUSE_TTS", "openai").lower() in {"openai", "gpt", "gpt-4o-tts"}:
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                client = OpenAI(api_key=api_key)

                # Voice: sage (default, new), nova, coral, ash, alloy, echo, fable, onyx, shimmer
                voice = os.getenv("CMPUSE_TTS_VOICE", "sage")
                model = os.getenv("CMPUSE_TTS_MODEL", "tts-1-hd")

                # Generate speech
                response = client.audio.speech.create(
                    model=model,
                    voice=voice,
                    input=text,
                    speed=1.0
                )

                # Save to temp file and play
                temp_dir = Path.home() / ".cmpuse" / "temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_file = temp_dir / f"speech_{hash(text)}.mp3"

                with open(temp_file, "wb") as f:
                    f.write(response.content)

                # Play audio
                if os.name == 'nt':  # Windows
                    os.startfile(str(temp_file))
                elif os.name == 'posix':  # macOS/Linux
                    if os.uname().sysname == 'Darwin':  # macOS
                        subprocess.run(["afplay", str(temp_file)])
                    else:  # Linux
                        for player in ["paplay", "aplay", "mpg123", "ffplay"]:
                            try:
                                subprocess.run([player, str(temp_file)], timeout=1)
                                break
                            except:
                                continue

                return True
        except Exception:
            pass

    # PRIORITY 2: Edge TTS if requested/available for a more natural voice
    if os.getenv("CMPUSE_TTS", "openai").lower() in {"edge", "edge-tts"}:
        try:
            import edge_tts  # type: ignore

            voice = os.getenv("CMPUSE_TTS_VOICE", "en-US-AriaNeural")
            async def _speak():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.stream(asyncio.get_event_loop())
            try:
                asyncio.run(_speak())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(_speak())
            return True
        except Exception:
            pass

    # Try pyttsx3 if available
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        # Try to select a female English voice if available (e.g., Zira)
        try:
            voices = engine.getProperty('voices')
            preferred = None
            for v in voices:
                name = (getattr(v, 'name', '') or '').lower()
                lang = ''.join(getattr(v, 'languages', [])).lower() if hasattr(v, 'languages') else ''
                if 'zira' in name or ('female' in name and ('en' in name or 'en' in lang)):
                    preferred = v
                    break
            if preferred:
                engine.setProperty('voice', preferred.id)
        except Exception:
            pass
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception:
        pass

    # Fallback to PowerShell SAPI if allowed
    if allow_shell or os.getenv("CMPUSE_ALLOW_SHELL", "0").lower() in {"1", "true", "yes", "on"}:
        try:
            phrase = text.replace("'", "''")
            ps_cmd = "$s=New-Object -ComObject SAPI.SpVoice; $s.Speak('{}')".format(phrase)
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                ps_cmd,
            ]
            subprocess.run(cmd, timeout=30)
            return True
        except Exception:
            return False
    return False
