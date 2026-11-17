"""Opt-in local face enrollment. Not an authentication system."""
import base64
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import FACE_NAME
import json
import os
import socket
import time
import cv2
import numpy as np
from body_bridge import status

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'models/face'
DATA = ROOT / 'private/face'
PROFILE = DATA / 'profile.npy'


def feature():
    detector_path = MODELS / 'yunet.onnx'
    recognizer_path = MODELS / 'sface.onnx'
    if not detector_path.is_file() or not recognizer_path.is_file():
        status('Face models are not ready — download in progress')
        raise ValueError('人臉模型尚未下載完成。')
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(10)
        client.connect('/tmp/yolo-vision.0.sock')
        client.sendall(b'{"action":"capture"}\n')
        with client.makefile('rb') as stream:
            result = json.loads(stream.readline(12_000_000))
    if result.get('status') != 'success':
        raise ValueError('攝影機擷取失敗。')
    image = cv2.imdecode(np.frombuffer(base64.b64decode(result['frame']), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('攝影機畫面無效。')
    h, w = image.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(detector_path), '', (w, h), 0.9)
    _, faces = detector.detect(image)
    if faces is None or len(faces) != 1:
        raise ValueError('請讓畫面中只有一張清楚的人臉，再試一次。')
    recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), '')
    vector = recognizer.feature(recognizer.alignCrop(image, faces[0])).flatten()
    return vector / np.linalg.norm(vector)


def run(action):
    try:
        if action == 'delete':
            PROFILE.unlink(missing_ok=True)
            return f'已刪除 {FACE_NAME} 的本機臉部特徵資料。'
        if action == 'enroll':
            if PROFILE.exists():
                return f'{FACE_NAME} 已有登錄資料。如需重新登錄，請先刪除我的臉。'
            vectors = []
            for index in range(3):
                status(f'Enrolling {FACE_NAME}: sample {index + 1}/3 — look at the camera')
                vectors.append(feature())
                time.sleep(0.4)
            DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(str(PROFILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                np.save(stream, np.stack(vectors), allow_pickle=False)
            return f'{FACE_NAME} 的臉部特徵已在本機登錄，不保存原始照片。請再說辨識我是誰測試。'
        if not PROFILE.exists():
            return '尚未登錄。請本人面向鏡頭，說登錄我的臉。'
        enrolled = np.load(PROFILE, allow_pickle=False)
        scores = []
        for index in range(3):
            status(f'Recognizing face: sample {index + 1}/3')
            scores.append(float(np.max(enrolled @ feature())))
            time.sleep(0.3)
        # Conservative initial threshold; must be evaluated in this environment.
        if min(scores) >= 0.5:
            return f'連續三次比對符合，可能是 {FACE_NAME}。這不是安全身分驗證，也不能排除照片。'
        return f'Unknown，目前無法確定是 {FACE_NAME}。'
    except (OSError, ValueError, KeyError, cv2.error) as error:
        status('Face task failed — see conversation for details')
        return f'人臉辨識未完成：{error}'
