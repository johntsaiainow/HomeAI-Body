#!/usr/bin/env python3
"""Background camera service with a newline/EOF-delimited Unix socket API."""

import base64
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import YOLO_MODEL
import fcntl
import json
import os
import socket

import cv2
from ultralytics import YOLO


class VisionDaemon:
    def __init__(self, device_id: int = 0):
        self.device_id = device_id
        self.socket_path = f"/tmp/yolo-vision.{device_id}.sock"
        self.running = False
        self.model = None
        self.cap = None

    def start(self):
        model_path = YOLO_MODEL
        self.model = YOLO(str(model_path))

    def capture_frame(self, raw: bool = False, preview: bool = False):
        cap = None
        try:
            if self.cap is None or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.device_id)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap = self.cap
            if not cap.isOpened():
                return {"status": "error", "message": f"Could not open camera device {self.device_id}"}
            ok, frame = cap.read()
            if not ok:
                return {"status": "error", "message": "Failed to read frame from camera"}
            height, width = frame.shape[:2]
            frame_info = {"width": width, "height": height}
            if raw:
                ok, encoded = cv2.imencode(".jpg", frame)
                if not ok:
                    return {"status": "error", "message": "Failed to encode frame"}
                return {"status": "success", "encoding": "jpeg", "frame_info": frame_info,
                        "frame": base64.b64encode(encoded.tobytes()).decode("ascii")}

            detections = []
            # Ultralytics accepts OpenCV's BGR arrays directly.
            for result in self.model(frame, verbose=False):
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                    detections.append({
                        "class_id": class_id,
                        "class_name": result.names.get(class_id, f"class_{class_id}"),
                        "confidence": round(float(box.conf[0]), 4),
                        "bbox": {"x1": round(x1 / width, 2), "y1": round(y1 / height, 2),
                                 "x2": round(x2 / width, 2), "y2": round(y2 / height, 2)},
                        "center": {"x": round((x1 + x2) / (2 * width), 4),
                                   "y": round((y1 + y2) / (2 * height), 4)},
                    })
            response = {"status": "success", "frame_info": frame_info, "detections": detections,
                        "count": len(detections), "message": f"Detected {len(detections)} object(s)"}
            if preview:
                ok, encoded = cv2.imencode('.jpg', frame)
                if not ok:
                    raise ValueError('Could not encode preview')
                response['frame'] = base64.b64encode(encoded.tobytes()).decode('ascii')
            return response
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            pass  # Reuse camera until service shutdown.


def handle_command(action, params, daemon):
    if action == 'preview':
        return daemon.capture_frame(preview=True)
    if action == "analyze":
        return daemon.capture_frame()
    if action == "capture":
        return daemon.capture_frame(raw=True)
    if action == "list_classes":
        return {"status": "success", "classes": list(daemon.model.names.values())}
    if action == "status":
        return {"status": "success", "action": "status", "running": daemon.running,
                "device_id": daemon.device_id}
    if action == "stop":
        daemon.running = False
        return {"status": "success", "action": "stop", "message": "Vision daemon stopped"}
    return {"status": "error", "message": f"Unknown action: {action}. Supported: analyze, capture, list_classes, status, stop"}


def run_daemon(device_id: int = 0):
    daemon = VisionDaemon(device_id)
    # Keep the lock file in place: unlinking a lock file can create multiple locks.
    with open(f"/tmp/yolo-vision.{device_id}.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"Vision daemon already running for device {device_id}", flush=True)
            return
        try:
            daemon.start()
        except Exception as e:
            print(f"Failed to initialize: {e}", flush=True)
            sys.exit(1)

        if os.path.exists(daemon.socket_path):
            os.remove(daemon.socket_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(daemon.socket_path)
            os.chmod(daemon.socket_path, 0o600)
            server.listen(8)
            server.settimeout(0.5)
            daemon.running = True
            print(f"Vision daemon listening on {daemon.socket_path}", flush=True)
            # Serial requests prevent concurrent access to the camera and model.
            while daemon.running:
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                with client:
                    client.settimeout(10)
                    try:
                        data = b""
                        while b"\n" not in data:
                            chunk = client.recv(4096)
                            if not chunk:
                                break
                            data += chunk
                            if len(data) > 65536:
                                raise ValueError("Request too large")
                        text = data.split(b"\n", 1)[0].decode("utf-8").strip()
                        try:
                            command = json.loads(text)
                        except json.JSONDecodeError:
                            command = text
                        if isinstance(command, dict):
                            action, params = command.get("action", "capture"), command.get("params", {})
                        elif isinstance(command, str):
                            action, params = command.lower(), {}
                        else:
                            raise ValueError("Command must be an object or string")
                        response = handle_command(action, params, daemon)
                    except Exception as e:
                        response = {"status": "error", "message": str(e)}
                    try:
                        client.sendall(json.dumps(response).encode("utf-8") + b"\n")
                    except OSError as e:
                        print(f"Could not send response: {e}", flush=True)
        finally:
            daemon.running = False
            if daemon.cap is not None:
                daemon.cap.release()
            server.close()
            if os.path.exists(daemon.socket_path):
                os.remove(daemon.socket_path)


if __name__ == "__main__":
    run_daemon(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
