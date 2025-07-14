from .core import skill
import base64

@skill
def capture_image(camera_index: int = 0):
    """Capture a single image from the default camera."""
    try:
        import cv2
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return {"error": "camera not available"}
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return {"error": "capture failed"}
        _, buf = cv2.imencode('.png', frame)
        return {"image": base64.b64encode(buf.tobytes()).decode()}
    except Exception as e:
        return {"error": str(e)}

@skill
def record_audio(duration: int = 3, sample_rate: int = 44100):
    """Record audio from the microphone."""
    try:
        import sounddevice as sd
        import numpy as np
        import io, wave
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())
        return {"audio": base64.b64encode(buf.getvalue()).decode()}
    except Exception as e:
        return {"error": str(e)}
