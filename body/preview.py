"""Fast shared-camera preview with optional same-frame detection boxes."""
import base64
import json
import socket
import sys
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt, QRectF, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QCheckBox


class Frames(QThread):
    frame = Signal(QImage, object)
    error = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.boxes = True

    def run(self):
        while not self.isInterruptionRequested():
            try:
                action = 'preview' if self.boxes else 'capture'
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(5)
                    client.connect('/tmp/yolo-vision.0.sock')
                    client.sendall((json.dumps({'action': action}) + '\n').encode())
                    with client.makefile('rb') as stream:
                        result = json.loads(stream.readline(12_000_000))
                if result.get('status') != 'success':
                    raise ValueError(result.get('message', 'Camera unavailable'))
                image = QImage.fromData(base64.b64decode(result['frame']))
                if image.isNull():
                    raise ValueError('Invalid frame')
                self.frame.emit(image, result.get('detections', []))
                self.msleep(40)
            except (OSError, ValueError, KeyError) as error:
                self.error.emit(f'Camera unavailable: {error}')
                self.msleep(500)


class Preview(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Neris-A · Camera Preview')
        self.resize(800, 600)
        self.image = QLabel('Connecting to camera…')
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(320, 240)
        self.toggle = QCheckBox('Show detection boxes')
        self.toggle.setChecked(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.image, 1)
        layout.addWidget(self.toggle)
        self.hand_status = QLabel('Hands: waiting for detector…')
        self.hand_status.setWordWrap(True)
        layout.addWidget(self.hand_status)
        self.hand_timer = QTimer(self)
        self.hand_timer.timeout.connect(self.update_hand_status)
        self.hand_timer.start(500)
        self.worker = Frames(self)
        self.toggle.toggled.connect(self.set_boxes)
        self.worker.frame.connect(self.show_frame)
        self.worker.error.connect(self.image.setText)
        self.settings_path = Path(__file__).resolve().parent / 'detection-boxes.json'
        self.sync_boxes()
        self.settings_timer = QTimer(self)
        self.settings_timer.timeout.connect(self.sync_boxes)
        self.settings_timer.start(300)
        self.worker.start()

    def update_hand_status(self):
        from datetime import datetime
        try:
            path = Path(__file__).resolve().parent / 'gesture-status.json'
            data = json.loads(path.read_text())
            age = (datetime.now().astimezone() - datetime.fromisoformat(data['time'])).total_seconds()
            if age > 5:
                self.hand_status.setText('Hands: detector data is stale')
                return
            candidates = ', '.join(f"{c['name']} {c['score']:.0%}" for c in data['candidates'])
            rules = ', '.join(data.get('rule_candidates', []))
            if rules:
                candidates = f'{rules} (rule)' + (f' / {candidates}' if candidates else '')
            text = f"Hands detected: {data['hands']}"
            if candidates:
                text += ' · ' + candidates
            elif data['hands'] == 0:
                text += ' · Show your whole hand, palm toward camera'
            if data['hands']:
                self.last_hand_text = text + ' · candidate, not confirmed'
                self.last_hand_time = datetime.now().timestamp()
            if datetime.now().timestamp() - getattr(self, 'last_hand_time', 0) < 4:
                text = self.last_hand_text
            self.hand_status.setText(text)
        except (OSError, ValueError, KeyError):
            self.hand_status.setText('Hands: detector not ready')

    def sync_boxes(self):
        try:
            enabled = json.loads(self.settings_path.read_text()).get('enabled', True)
            if isinstance(enabled, bool):
                self.toggle.blockSignals(True)
                self.toggle.setChecked(enabled)
                self.toggle.blockSignals(False)
                self.worker.boxes = enabled
        except (OSError, ValueError, AttributeError):
            pass

    def set_boxes(self, checked):
        self.worker.boxes = checked
        try:
            temporary = self.settings_path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'enabled': checked}))
            temporary.replace(self.settings_path)
        except OSError:
            pass

    def show_frame(self, image, detections):
        if self.toggle.isChecked():
            painter = QPainter(image)
            painter.setPen(QPen(QColor('#00ff66'), 2))
            for item in detections:
                if item.get('confidence', 0) < 0.4:
                    continue
                box = item['bbox']
                x, y = box['x1'] * image.width(), box['y1'] * image.height()
                painter.drawRect(QRectF(x, y,
                    (box['x2'] - box['x1']) * image.width(),
                    (box['y2'] - box['y1']) * image.height()))
                painter.drawText(int(x), max(15, int(y) - 5),
                                 f"{item['class_name']} {item['confidence']:.0%}")
            painter.end()
        self.image.setPixmap(QPixmap.fromImage(image).scaled(
            self.image.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def closeEvent(self, event):
        self.worker.requestInterruption()
        self.worker.wait(6500)
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Preview()
    window.show()
    screen = window.screen().availableGeometry()
    window.resize(min(800, max(320, screen.width() // 2 - 24)),
                  min(650, screen.height() - 32))
    window.move(screen.x() + screen.width() // 2 + 12, screen.y() + 16)
    sys.exit(app.exec())
