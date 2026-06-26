from __future__ import annotations

import threading
import time
from typing import Callable, Optional


class VoiceLoop:
    def __init__(self, wake_word: str = "ava", on_utterance: Optional[Callable[[str], None]] = None) -> None:
        self.wake_word = wake_word.lower()
        self.on_utterance = on_utterance
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        try:
            import speech_recognition as sr  # type: ignore
        except Exception:
            return False

        def _run():
            r = sr.Recognizer()
            r.dynamic_energy_threshold = True
            r.pause_threshold = 0.6
            mic = None
            try:
                mic = sr.Microphone()
            except Exception:
                return
            with mic as source:
                try:
                    r.adjust_for_ambient_noise(source, duration=1)
                except Exception:
                    pass
                while not self._stop.is_set():
                    try:
                        audio = r.listen(source, timeout=None, phrase_time_limit=10)
                        text = ""
                        try:
                            # Prefer offline Sphinx if installed; else fall back to Google (needs network)
                            try:
                                text = r.recognize_sphinx(audio)  # type: ignore[attr-defined]
                            except Exception:
                                text = r.recognize_google(audio)
                        except Exception:
                            continue
                        norm = " ".join(text.lower().split())
                        if self.wake_word in norm:
                            # Strip wake word and punctuation around it
                            utter = norm.replace(self.wake_word, "").strip(" ,.!?;:")
                            if not utter:
                                # If nothing follows wake word, pass full text
                                utter = norm
                            if self.on_utterance:
                                self.on_utterance(utter)
                    except Exception:
                        time.sleep(0.25)

        self._stop.clear()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None

