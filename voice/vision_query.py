"""On-demand object detection through the existing camera skill."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import VOICE_PYTHON, CAMERA_SCRIPT
import subprocess
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'body'))
import speech_service


def describe():
    language = speech_service.selected()
    english = language == "en"

    def message(zh, en):
        return en if english else zh

    try:
        result = subprocess.run(
            [str(VOICE_PYTHON), '-B',
             str(CAMERA_SCRIPT), 'analyze'],
            capture_output=True, text=True, timeout=70)

        if result.returncode:
            return message(
                '攝影機辨識目前失敗，請檢查攝影機服務。',
                'Camera recognition failed. Please check the camera service.')

        data = json.loads(result.stdout)

        if data.get('status') != 'success':
            return message(
                '攝影機辨識目前失敗。',
                'Camera recognition failed.')

        objects = Counter(
            item['class_name']
            for item in data.get('detections', [])
            if item.get('confidence', 0) >= 0.4
        )

        if not objects:
            return message(
                '這次沒有辨識到足夠確定的物件，不代表前方沒有東西。',
                'I could not confidently identify any objects. '
                'That does not mean nothing is there.')

        names = {
            'person': '人', 'chair': '椅子',
            'bottle': '瓶子', 'cup': '杯子',
            'laptop': '筆記型電腦', 'tv': '螢幕',
            'cell phone': '手機', 'keyboard': '鍵盤',
            'mouse': '滑鼠', 'book': '書',
            'cat': '貓', 'dog': '狗',
            'dining table': '桌子'
        }

        if english:
            text = ', '.join(
                f'{count} {name}'
                for name, count in objects.most_common(8)
            )
            return (
                f'The camera detected: {text}. '
                'Object detection may not always be accurate.'
            )

        text = '、'.join(
            f'{count} 個{names.get(name, name)}'
            for name, count in objects.most_common(8)
        )

        return (
            f'這次攝影機辨識到：{text}。'
            '這是物件偵測結果，可能有誤判。'
        )

    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return message(
            '攝影機辨識暫時無法完成，請稍後再試。',
            'Camera recognition is temporarily unavailable. '
            'Please try again later.')
