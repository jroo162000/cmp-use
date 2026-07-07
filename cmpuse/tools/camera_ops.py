"""
Camera & Video Processing - Webcam capture, face detection, video analysis, real-time monitoring
Includes continuous vision monitoring for AVA to "see" in real-time
"""

from .._lazyimport import lazy_module, LazyInstance
cv2 = lazy_module("cv2")          # heavy: imported on first actual use, not at module load
mp = lazy_module("mediapipe")     # heavy (slowest import); deferred
np = lazy_module("numpy")
import os as _os


# ── Shared live frame (published by ava-integration/gaze_tracker.py) ─────────
# The gaze tracker owns the webcam around the clock and publishes its latest
# 720p frame every ~0.5s. Snapshot-style captures READ that frame instead of
# opening the device (which would fail or steal it). Direct device access is
# the automatic fallback when the tracker is off (AVA_GAZE_OFF=1) or stale.
_LIVE_FRAME_PATH = _os.path.join(_os.path.expanduser("~"), ".cmpuse", "camera_live.jpg")  # note: only _os exists this early in the module
_LIVE_FRAME_MAX_AGE_S = 3.0

def _read_live_frame():
    """Return (frame, age_s) from the tracker's shared frame, or (None, None)."""
    try:
        st = os.stat(_LIVE_FRAME_PATH)
        age = time.time() - st.st_mtime
        if age > _LIVE_FRAME_MAX_AGE_S or st.st_size < 1000:
            return None, None
        frame = cv2.imread(_LIVE_FRAME_PATH)
        if frame is None or frame.size == 0:
            return None, None
        return frame, age
    except Exception:
        return None, None

def _preferred_camera_name():
    # Which physical camera to prefer (substring match, case-insensitive). Defaults to
    # the user's Logitech; override with the AVA_CAMERA env var.
    return (_os.getenv("AVA_CAMERA") or "logi").lower()


def _resolve_camera_index(requested=0):
    """Resolve which camera index to open. If a specific non-zero index is requested,
    honor it. Otherwise pick the PREFERRED camera by name (e.g. the Logitech) so we
    don't grab the wrong/default webcam; fall back to the first index that opens."""
    try:
        if requested and int(requested) != 0:
            return int(requested)
    except Exception:
        pass
    pref = _preferred_camera_name()
    # 1) Match by DirectShow device name (preferred).
    try:
        from pygrabber.dshow_graph import FilterGraph
        names = FilterGraph().get_input_devices()
        for i, n in enumerate(names):
            if pref in (n or "").lower():
                return i
    except Exception:
        pass
    # 2) Fallback: first index that actually opens via DirectShow.
    try:
        for i in range(6):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            ok = bool(cap.isOpened())
            cap.release()
            if ok:
                return i
    except Exception:
        pass
    return int(requested) if requested else 0


def _default_camera_path():
    from datetime import datetime as _dt
    d = _os.path.join(_os.path.expanduser("~"), "Pictures", "AVA_Camera")
    try:
        _os.makedirs(d, exist_ok=True)
    except Exception:
        d = _os.path.expanduser("~")
    return _os.path.join(d, f"camera_{_dt.now().strftime('%Y%m%d_%H%M%S')}.jpg")


def _describe_image_file(path):
    """Describe an image via the shared vision provider fallback chain (OpenAI -> Gemini ->
    Claude), so the camera's 'see' doesn't die when one provider is over quota. Returns a
    description string, or None if no vision provider is available."""
    try:
        try:
            from cmpuse.secrets import load_into_env as _ls
            _ls()  # load API keys from ~/.cmpuse/secrets.json into env
        except Exception:
            pass
        question = ("Describe what is shown in this image in 1-3 short, natural sentences: the "
                    "setting, lighting, colors, and the main objects or activity visible. You may "
                    "note generally if a person is present (e.g. 'someone is at a desk'), without "
                    "identifying who they are.")
        try:
            from cmpuse.tools.vision_ops import _describe_image as _vision
        except Exception:
            _vision = None
        with open(path, "rb") as f:
            data = f.read()
        low = str(path).lower()
        mime = "image/jpeg" if low.endswith((".jpg", ".jpeg")) else ("image/webp" if low.endswith(".webp") else "image/png")
        if _vision is not None:
            r = _vision(data, question, mime)
            if r.get("ok"):
                return r["text"]
        return None
    except Exception:
        return None
from datetime import datetime
import os
import threading
import time
import base64
import tempfile
from typing import Any, Dict, List, Optional
from collections import deque
from ..tool_registry import Tool, register


class VisionMonitor:
    """
    Continuous vision monitoring system.
    Runs in background, captures frames periodically, analyzes them, stores observations.
    """

    def __init__(self, max_observations: int = 50):
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.camera = None
        self.camera_index = 0
        self.observations: deque = deque(maxlen=max_observations)
        self.current_scene: Dict[str, Any] = {}
        self.analysis_interval = 3.0  # seconds between AI analysis
        self.capture_interval = 0.5   # seconds between frame captures
        self.last_analysis_time = 0
        self.last_frame_path: Optional[str] = None
        self.lock = threading.Lock()
        self._stop_event = threading.Event()

        # For local detection (fast, no API calls)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        # mediapipe is heavy + optional; guard so capture/see/monitoring work with cv2
        # alone. Pose/face-mesh detection lazily needs mediapipe only when actually used.
        try:
            self.mp_face_detection = mp.solutions.face_detection
            self.mp_pose = mp.solutions.pose
        except Exception:
            self.mp_face_detection = None
            self.mp_pose = None

        # Track what we've seen
        self.faces_detected = 0
        self.motion_detected = False
        self.last_frame = None
        self.scene_changed = False

    def start(self, camera_index: int = 0) -> Dict[str, Any]:
        """Start continuous monitoring"""
        if self.is_monitoring:
            return {"status": "ok", "message": "Already monitoring"}

        # Pick the preferred physical camera (e.g. the Logitech), not default index 0.
        camera_index = _resolve_camera_index(camera_index)
        self.camera_index = camera_index
        # DirectShow backend: the default MSMF backend can BLOCK ~30s when opening the
        # camera (which timed out "turn on the camera"); DSHOW returns promptly.
        try:
            self.camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        except Exception:
            self.camera = cv2.VideoCapture(camera_index)

        if not self.camera or not self.camera.isOpened():
            return {"status": "error", "message": f"Could not open camera {camera_index} (no camera detected)"}

        self._stop_event.clear()
        self.is_monitoring = True
        self.observations.clear()
        self.current_scene = {}

        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        return {
            "status": "ok",
            "message": "Vision monitoring started. I can now see continuously.",
            "camera_index": camera_index
        }

    def stop(self) -> Dict[str, Any]:
        """Stop continuous monitoring"""
        if not self.is_monitoring:
            return {"status": "ok", "message": "Not currently monitoring"}

        self._stop_event.set()
        self.is_monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None

        if self.camera:
            self.camera.release()
            self.camera = None

        return {"status": "ok", "message": "Vision monitoring stopped. Camera closed."}

    def _monitor_loop(self):
        """Background loop that continuously monitors the camera"""
        motion_threshold = 5000

        while not self._stop_event.is_set():
            try:
                if not self.camera or not self.camera.isOpened():
                    break

                ret, frame = self.camera.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                current_time = time.time()

                # Quick local analysis (every frame)
                with self.lock:
                    # Detect faces locally (fast)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                    self.faces_detected = len(faces)

                    # Detect motion
                    if self.last_frame is not None:
                        diff = cv2.absdiff(self.last_frame, gray)
                        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                        motion_score = np.sum(thresh) / 255
                        self.motion_detected = motion_score > motion_threshold
                        self.scene_changed = motion_score > (motion_threshold * 2)

                    self.last_frame = gray.copy()

                    # Save current frame for potential analysis
                    temp_dir = tempfile.gettempdir()
                    self.last_frame_path = os.path.join(temp_dir, "ava_vision_current.png")
                    cv2.imwrite(self.last_frame_path, frame)

                    # Update current scene state
                    self.current_scene = {
                        "timestamp": datetime.now().isoformat(),
                        "faces_visible": self.faces_detected,
                        "motion_detected": self.motion_detected,
                        "scene_changed": self.scene_changed
                    }

                    # Add observation if something interesting happened
                    if self.faces_detected > 0 or self.motion_detected:
                        observation = {
                            "time": datetime.now().isoformat(),
                            "faces": self.faces_detected,
                            "motion": self.motion_detected,
                            "type": "local_detection"
                        }
                        self.observations.append(observation)

                time.sleep(self.capture_interval)

            except Exception as e:
                print(f"[vision-monitor] Error in loop: {e}")
                time.sleep(1.0)

        print("[vision-monitor] Monitor loop ended")

    def get_current_frame_path(self) -> Optional[str]:
        """Get path to the most recent captured frame"""
        with self.lock:
            return self.last_frame_path

    def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        with self.lock:
            return {
                "is_monitoring": self.is_monitoring,
                "current_scene": self.current_scene.copy() if self.current_scene else {},
                "observations_count": len(self.observations),
                "last_frame_path": self.last_frame_path
            }

    def get_observations(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent observations"""
        with self.lock:
            obs_list = list(self.observations)
            return obs_list[-count:] if len(obs_list) > count else obs_list

    def add_ai_observation(self, description: str):
        """Add an AI-generated observation"""
        with self.lock:
            self.observations.append({
                "time": datetime.now().isoformat(),
                "type": "ai_analysis",
                "description": description
            })

    def get_summary(self) -> str:
        """Get a text summary of what has been observed"""
        with self.lock:
            if not self.observations:
                return "I haven't observed anything notable yet."

            # Count observations
            face_observations = [o for o in self.observations if o.get("faces", 0) > 0]
            motion_observations = [o for o in self.observations if o.get("motion", False)]
            ai_observations = [o for o in self.observations if o.get("type") == "ai_analysis"]

            summary_parts = []

            if face_observations:
                summary_parts.append(f"I've detected faces {len(face_observations)} times")

            if motion_observations:
                summary_parts.append(f"noticed motion {len(motion_observations)} times")

            if ai_observations:
                # Include the most recent AI observation
                latest_ai = ai_observations[-1]
                summary_parts.append(f"My latest observation: {latest_ai.get('description', '')}")

            if summary_parts:
                return ". ".join(summary_parts) + "."
            else:
                return "The scene has been relatively static."


# Global vision monitor instance (constructed lazily on first use — its __init__
# touches cv2/mediapipe, which we don't want to run at import time).
vision_monitor = LazyInstance(VisionMonitor)

class CameraManager:
    def __init__(self):
        self.camera = None
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        # mediapipe is heavy + optional; guard so capture/see work with cv2 alone.
        # detect_hands/pose/face-mesh lazily require mediapipe only when actually used.
        try:
            self.mp_hands = mp.solutions.hands
            self.mp_face_detection = mp.solutions.face_detection
            self.mp_pose = mp.solutions.pose
        except Exception:
            self.mp_hands = None
            self.mp_face_detection = None
            self.mp_pose = None
        self.recording = False

    def open_camera(self, camera_index=0):
        """Open camera for capture"""
        if not self.camera or not self.camera.isOpened():
            # Pick the preferred physical camera (e.g. the Logitech) instead of the
            # default index 0, which may be the wrong/unavailable webcam.
            camera_index = _resolve_camera_index(camera_index)
            # The default Windows MSMF backend can BLOCK for a long time when no camera
            # is present; DirectShow (CAP_DSHOW) returns promptly with isOpened()=False
            # so we fail fast with a clear message instead of hanging the worker.
            try:
                self.camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            except Exception:
                self.camera = cv2.VideoCapture(camera_index)
            if not self.camera or not self.camera.isOpened():
                raise Exception(f"Could not open camera {camera_index} (no camera detected)")
        return self.camera

    def close_camera(self):
        """Release camera"""
        if self.camera:
            self.camera.release()
            self.camera = None

    def capture_frame(self):
        """Capture a single frame. Prefers the gaze tracker's shared live frame
        (the tracker owns the webcam; grabbing the device here would conflict);
        falls back to opening the device directly when the tracker is off."""
        frame, age = _read_live_frame()
        if frame is not None:
            return frame

        if not self.camera or not self.camera.isOpened():
            self.open_camera()

        ret, frame = self.camera.read()
        if not ret:
            raise Exception("Failed to capture frame")

        return frame

    def detect_faces(self, frame):
        """Detect faces in frame using OpenCV"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)

        results = []
        for (x, y, w, h) in faces:
            results.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "confidence": 0.9  # Haar cascade doesn't provide confidence
            })

        return results

    def detect_faces_mediapipe(self, frame):
        """Detect faces using MediaPipe (more accurate)"""
        with self.mp_face_detection.FaceDetection(min_detection_confidence=0.5) as face_detection:
            results = face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            if not results.detections:
                return []

            faces = []
            h, w, _ = frame.shape
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                faces.append({
                    "x": int(bbox.xmin * w),
                    "y": int(bbox.ymin * h),
                    "width": int(bbox.width * w),
                    "height": int(bbox.height * h),
                    "confidence": detection.score[0]
                })

            return faces

    def detect_hands(self, frame):
        """Detect hands using MediaPipe"""
        with self.mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            if not results.multi_hand_landmarks:
                return []

            hand_data = []
            for hand_landmarks in results.multi_hand_landmarks:
                landmarks = []
                for landmark in hand_landmarks.landmark:
                    landmarks.append({
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z
                    })
                hand_data.append({"landmarks": landmarks})

            return hand_data

    def detect_pose(self, frame):
        """Detect human pose using MediaPipe"""
        with self.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            if not results.pose_landmarks:
                return None

            landmarks = []
            for landmark in results.pose_landmarks.landmark:
                landmarks.append({
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z,
                    "visibility": landmark.visibility
                })

            return {"landmarks": landmarks}

camera_manager = LazyInstance(CameraManager)

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "capture")

    if action == "capture":
        return {"preview": "Capture webcam frame", "args": args}
    elif action == "detect_faces":
        return {"preview": "Detect faces in webcam", "args": args}
    elif action == "detect_hands":
        return {"preview": "Detect hands in webcam", "args": args}
    elif action == "detect_pose":
        return {"preview": "Detect human pose", "args": args}
    elif action == "start_monitoring":
        return {"preview": "Start continuous vision monitoring", "args": args}
    elif action == "stop_monitoring":
        return {"preview": "Stop continuous vision monitoring", "args": args}
    elif action == "get_observations":
        return {"preview": "Get accumulated vision observations", "args": args}
    elif action == "get_current_frame":
        return {"preview": "Get path to current frame for analysis", "args": args}
    elif action == "analyze_video":
        return {"preview": f"Analyze video file", "args": args}
    else:
        return {"preview": f"Camera action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform camera operation", "plan": _plan(args)}

    action = args.get("action", "capture")

    # "start the camera and tell me what you see" -> the model often passes action="start".
    # For a voice assistant, starting/opening the camera to look means: capture AND describe.
    if str(action).lower() in ("start", "start_camera", "activate", "on", "turn_on", "open", "open_camera", "use_camera", "view", "watch"):
        action = "see"

    # Recognized actions (kept in this form so schema introspection discovers them):
    # action == "capture"; action == "see"; action == "describe"; action == "look"
    # action == "record_video"; action == "record"
    try:
        if action == "capture":
            camera_index = args.get("camera_index", 0)
            save_path = args.get("save_path")

            frame = camera_manager.capture_frame()

            if save_path:
                cv2.imwrite(save_path, frame)
                file_size = os.path.getsize(save_path) / 1024  # KB
                return {
                    "status": "ok",
                    "message": f"Frame captured and saved",
                    "file_path": save_path,
                    "size_kb": round(file_size, 2),
                    "dimensions": f"{frame.shape[1]}x{frame.shape[0]}"
                }
            else:
                # No path given: save to a findable default so the user can locate it.
                save_path = _default_camera_path()
                cv2.imwrite(save_path, frame)
                return {
                    "status": "ok",
                    "message": f"Frame captured and saved to {save_path}",
                    "file_path": save_path,
                    "dimensions": f"{frame.shape[1]}x{frame.shape[0]}"
                }

        elif action in ("see", "describe", "look", "what_do_you_see", "describe_view"):
            # Capture from the (Logitech) camera, save it, and DESCRIBE what's in view.
            save_path = args.get("save_path") or _default_camera_path()
            frame = camera_manager.capture_frame()
            cv2.imwrite(save_path, frame)
            desc = _describe_image_file(save_path)
            if desc:
                return {
                    "status": "ok",
                    "message": desc,
                    "description": desc,
                    "file_path": save_path,
                    "dimensions": f"{frame.shape[1]}x{frame.shape[0]}"
                }
            return {
                "status": "ok",
                "message": f"I captured an image from the camera (saved to {save_path}), but I couldn't run vision describe (OpenAI key not available).",
                "file_path": save_path
            }

        elif action in ("record_video", "record", "start_recording", "capture_video"):
            # Record N seconds of video from the (Logitech) camera to a findable file.
            import time as _t
            from datetime import datetime as _dt
            try:
                duration = float(args.get("duration", args.get("seconds", 5)) or 5)
            except Exception:
                duration = 5.0
            duration = max(1.0, min(duration, 30.0))  # clamp 1-30s (stay under worker timeout)
            try:
                fps = int(args.get("fps", 20) or 20)
            except Exception:
                fps = 20
            fps = max(5, min(fps, 30))
            save_path = args.get("save_path")
            if not save_path:
                d = _os.path.join(_os.path.expanduser("~"), "Pictures", "AVA_Camera")
                try:
                    _os.makedirs(d, exist_ok=True)
                except Exception:
                    d = _os.path.expanduser("~")
                save_path = _os.path.join(d, f"video_{_dt.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            # Release any camera the manager/monitor holds so the device isn't busy.
            try:
                if getattr(camera_manager, "camera", None) is not None:
                    camera_manager.camera.release()
                    camera_manager.camera = None
            except Exception:
                pass
            idx = _resolve_camera_index(args.get("camera_index", 0))
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return {"status": "error", "message": "Could not open the camera to record."}
            for _ in range(5):
                cap.read()  # warm up
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                return {"status": "error", "message": "Camera opened but returned no frames."}
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            if not writer.isOpened():
                save_path = _os.path.splitext(save_path)[0] + ".avi"
                writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*"XVID"), fps, (w, h))
            interval = 1.0 / fps
            start = _t.time()
            next_t = start
            n = 0
            while _t.time() - start < duration:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                writer.write(frame)
                n += 1
                next_t += interval
                slp = next_t - _t.time()
                if slp > 0:
                    _t.sleep(slp)
            writer.release()
            cap.release()
            size_kb = round(_os.path.getsize(save_path) / 1024, 1) if _os.path.exists(save_path) else 0
            return {
                "status": "ok",
                "message": f"Recorded a {round(duration,1)}-second video ({n} frames) and saved it to {save_path}",
                "file_path": save_path,
                "duration_s": round(duration, 1),
                "frames": n,
                "size_kb": size_kb,
                "dimensions": f"{w}x{h}",
            }

        elif action == "detect_faces":
            use_mediapipe = args.get("use_mediapipe", True)
            save_annotated = args.get("save_annotated")

            frame = camera_manager.capture_frame()

            if use_mediapipe:
                faces = camera_manager.detect_faces_mediapipe(frame)
            else:
                faces = camera_manager.detect_faces(frame)

            # Optionally save annotated frame
            if save_annotated:
                for face in faces:
                    cv2.rectangle(frame, (face['x'], face['y']),
                                (face['x'] + face['width'], face['y'] + face['height']),
                                (0, 255, 0), 2)
                cv2.imwrite(save_annotated, frame)

            return {
                "status": "ok",
                "faces": faces,
                "count": len(faces),
                "message": f"Detected {len(faces)} face(s)"
            }

        elif action == "detect_hands":
            save_annotated = args.get("save_annotated")

            frame = camera_manager.capture_frame()
            hands = camera_manager.detect_hands(frame)

            if save_annotated and hands:
                # Draw hand landmarks
                with camera_manager.mp_hands.Hands() as hand_detector:
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame,
                        hands[0],
                        camera_manager.mp_hands.HAND_CONNECTIONS
                    )
                cv2.imwrite(save_annotated, frame)

            return {
                "status": "ok",
                "hands": hands,
                "count": len(hands),
                "message": f"Detected {len(hands)} hand(s)"
            }

        elif action == "detect_pose":
            save_annotated = args.get("save_annotated")

            frame = camera_manager.capture_frame()
            pose = camera_manager.detect_pose(frame)

            return {
                "status": "ok",
                "pose": pose,
                "detected": pose is not None,
                "message": "Pose detected" if pose else "No pose detected"
            }

        elif action == "close":
            # Also stop monitoring if active
            if vision_monitor.is_monitoring:
                vision_monitor.stop()
            camera_manager.close_camera()
            return {"status": "ok", "message": "Camera closed"}

        elif action == "start_monitoring":
            camera_index = args.get("camera_index", 0)
            result = vision_monitor.start(camera_index)
            return {
                "status": result.get("status", "error"),
                "message": result.get("message", ""),
                "monitoring": vision_monitor.is_monitoring
            }

        elif action == "stop_monitoring":
            result = vision_monitor.stop()
            return {
                "status": result.get("status", "error"),
                "message": result.get("message", ""),
                "monitoring": vision_monitor.is_monitoring
            }

        elif action == "get_observations":
            count = args.get("count", 10)
            status = vision_monitor.get_status()
            observations = vision_monitor.get_observations(count)
            summary = vision_monitor.get_summary()
            return {
                "status": "ok",
                "is_monitoring": status.get("is_monitoring", False),
                "current_scene": status.get("current_scene", {}),
                "observations": observations,
                "summary": summary,
                "message": summary
            }

        elif action == "get_current_frame":
            if not vision_monitor.is_monitoring:
                return {"status": "error", "message": "Vision monitoring not active. Start monitoring first."}
            frame_path = vision_monitor.get_current_frame_path()
            if frame_path and os.path.exists(frame_path):
                return {
                    "status": "ok",
                    "frame_path": frame_path,
                    "current_scene": vision_monitor.get_status().get("current_scene", {}),
                    "message": "Current frame available for analysis"
                }
            return {"status": "error", "message": "No frame available yet"}

        elif action == "add_observation":
            # Allow adding AI-generated observations from external analysis
            description = args.get("description", "")
            if description:
                vision_monitor.add_ai_observation(description)
                return {"status": "ok", "message": "Observation recorded"}
            return {"status": "error", "message": "No description provided"}

        elif action == "analyze_motion":
            duration = args.get("duration", 5)  # seconds
            threshold = args.get("threshold", 5000)

            camera_manager.open_camera()
            ret, frame1 = camera_manager.camera.read()
            ret, frame2 = camera_manager.camera.read()

            motion_events = []
            start_time = datetime.now()

            while (datetime.now() - start_time).seconds < duration:
                diff = cv2.absdiff(frame1, frame2)
                gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                blur = cv2.GaussianBlur(gray, (5, 5), 0)
                _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
                dilated = cv2.dilate(thresh, None, iterations=3)
                contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                motion_score = sum([cv2.contourArea(c) for c in contours])

                if motion_score > threshold:
                    motion_events.append({
                        "timestamp": datetime.now().isoformat(),
                        "score": motion_score
                    })

                frame1 = frame2
                ret, frame2 = camera_manager.camera.read()

            return {
                "status": "ok",
                "motion_events": motion_events,
                "count": len(motion_events),
                "message": f"Detected {len(motion_events)} motion events in {duration} seconds"
            }

        elif action == "analyze_video":
            video_path = args.get("video_path")
            detect_type = args.get("detect_type", "faces")  # faces, hands, pose

            if not video_path:
                return {"status": "error", "message": "video_path required"}

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {"status": "error", "message": f"Could not open video: {video_path}"}

            frame_count = 0
            detections_per_frame = []

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                if detect_type == "faces":
                    detections = camera_manager.detect_faces_mediapipe(frame)
                elif detect_type == "hands":
                    detections = camera_manager.detect_hands(frame)
                elif detect_type == "pose":
                    detections = [camera_manager.detect_pose(frame)] if camera_manager.detect_pose(frame) else []

                detections_per_frame.append({
                    "frame": frame_count,
                    "detections": len(detections)
                })

                # Sample every 10 frames to speed up
                for _ in range(9):
                    cap.read()
                frame_count += 9

            cap.release()

            avg_detections = sum([d["detections"] for d in detections_per_frame]) / len(detections_per_frame) if detections_per_frame else 0

            return {
                "status": "ok",
                "total_frames": frame_count,
                "sampled_frames": len(detections_per_frame),
                "average_detections": round(avg_detections, 2),
                "message": f"Analyzed {frame_count} frames"
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Camera ops error: {str(e)}"}

TOOL = Tool(
    name="camera_ops",
    summary=("Camera & vision. To SEE / describe what's in front of the webcam — ANY request to look, see, "
             "or describe (e.g. 'what do you see', 'look through the camera and tell me what you see', "
             "'start the camera and tell me what you see', 'describe what's in front of the camera', 'who is in front of the camera') "
             "— use action=see. It turns on the camera, captures a frame, AND describes it in one step; do NOT use capture for a describe request, "
             "and do NOT ask the user to confirm. action=capture just saves a photo. "
             "To RECORD a video clip (e.g. 'record a 5 second video'): use action=record_video with optional duration (default 5). "
             "NOTE: analyze_video is only for analyzing an EXISTING video file (needs video_path) — do NOT use it to record. "
             "Also: detect_faces, detect_hands, detect_pose, analyze_motion, start_monitoring/stop_monitoring. "
             "Photos and videos save to ~/Pictures/AVA_Camera by default."),
    plan=_plan,
    run=_run,
)

register(TOOL)
