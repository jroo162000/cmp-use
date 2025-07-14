import logging


def speak(text: str) -> None:
    """Speak text using pyttsx3 if available."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logging.getLogger(__name__).warning(f"TTS failed: {e}")


def listen() -> str:
    """Transcribe speech from the microphone using SpeechRecognition."""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.Microphone() as source:
            audio = r.listen(source)
        # Using Google's free recognizer as a fallback
        return r.recognize_google(audio)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Voice input failed: {e}")
        return ""
