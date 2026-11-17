"""Optional upper-right camera panel, sharing the existing vision socket."""
import json
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QTimer,Signal
from PySide6.QtGui import QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QSizePolicy
from preview import Frames

class CameraPanel(QWidget):
    hide_requested=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.wanted=False
        self.last_image=None
        self.frames_received=0
        self.last_error=None
        self.setFixedHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(8,4,8,4)
        header=QHBoxLayout()
        header.addWidget(QLabel('Camera Preview'),1)
        close=QPushButton('Hide')
        close.clicked.connect(lambda: self.hide_requested.emit())
        header.addWidget(close)
        layout.addLayout(header)
        self.image=QLabel('Connecting to camera…')
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored)
        self.image.setStyleSheet('background: black; color: white;')
        layout.addWidget(self.image,1)
        self.worker=Frames(self)
        self.worker.frame.connect(self.show_frame)
        self.worker.error.connect(self.show_error)
        self.worker.finished.connect(self.restart_if_needed)
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.sync_boxes)
        self.timer.start(300)
        self.sync_boxes()
        self.hide()

    def set_enabled(self,enabled):
        self.wanted=bool(enabled)
        self.setVisible(self.wanted)
        if self.wanted:
            self.restart_if_needed()
        else:
            self.worker.requestInterruption()

    def restart_if_needed(self):
        if self.wanted and not self.worker.isRunning():self.worker.start()

    def sync_boxes(self):
        try:
            self.worker.boxes=json.loads((Path(__file__).parent/'detection-boxes.json').read_text()).get('enabled',True) is True
        except (OSError,ValueError,AttributeError):pass

    def show_error(self,message):
        if self.wanted:
            self.last_image=None
            self.last_error=message
            self.image.setText(message)

    def show_frame(self,image,detections):
        if not self.wanted:return
        self.frames_received+=1
        self.last_error=None
        if self.worker.boxes:
            painter=QPainter(image)
            painter.setPen(QPen(QColor('#00ff66'),2))
            for item in detections:
                if item.get('confidence',0)<.4:continue
                box=item['bbox'];x=box['x1']*image.width();y=box['y1']*image.height()
                painter.drawRect(QRectF(x,y,(box['x2']-box['x1'])*image.width(),(box['y2']-box['y1'])*image.height()))
                painter.drawText(int(x),max(15,int(y)-5),f"{item['class_name']} {item['confidence']:.0%}")
            painter.end()
        self.last_image=image
        self.update_image()

    def update_image(self):
        if self.last_image is not None:
            self.image.setPixmap(QPixmap.fromImage(self.last_image).scaled(self.image.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fit_height()
        self.update_image()

    def fit_height(self):
        # Reserve space for the fixed controls even on shorter screens.
        available=self.window().height()
        height=min(380,max(160,int(available*.34)),max(160,int(self.width()*9/16)+42))
        if self.height()!=height:
            self.setFixedHeight(height)

    def shutdown(self):
        self.wanted=False
        self.timer.stop()
        self.worker.requestInterruption()
        self.worker.wait(6500)
