"""Read music IPC off the GUI thread; never owns or changes playback."""
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QCheckBox,QComboBox,QPushButton,QSizePolicy
from concurrent.futures import ThreadPoolExecutor
import time
from lyrics import Lyrics,local_audio,sidecar
import lyrics_download
from lyrics_choices import choices,choose
import music

class LyricsWorker(QThread):
    changed=Signal(object)
    candidates_changed=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.manual=None
    def run(self):
        engine=Lyrics();last=None;previous=None;attempted=None;notice=None
        future=None;future_song=None;metadata_next=0;last_choices=None
        pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='lyrics-lookup')
        try:
            while not self.isInterruptionRequested():
                path=music.request(['get_property','path'])
                filename=path.get('data') if path else None
                position=music.request(['get_property','time-pos']) if filename else None
                value=engine.update(filename,position.get('data') if position else None)
                if filename!=previous:
                    if filename:music.remember(filename)
                    previous=filename;attempted=None;notice=None;metadata_next=0
                if future is not None and future.done():
                    try:result=future.result()
                    except Exception:result='Lyrics lookup failed'
                    if future_song==filename:notice=result
                    future=None;last_choices=None
                auto=lyrics_download.enabled()
                if self.manual is not None and future is None:
                    song,identifier=self.manual;self.manual=None
                    future_song=song;attempted=song
                    future=pool.submit(choose,song,identifier);notice=None
                if not auto:
                    attempted=None;notice=None
                audio=local_audio(filename)
                missing=audio is not None and not engine.entries and not sidecar(audio)
                if auto and missing and future is None and attempted!=filename and time.monotonic()>=metadata_next:
                    metadata_next=time.monotonic()+5
                    tags=music.request(['get_property','metadata'])
                    duration=music.request(['get_property','duration'])
                    metadata=tags.get('data') if tags else {}
                    seconds=duration.get('data') if duration else None
                    if lyrics_download.identity(audio,metadata,seconds):
                        attempted=filename;future_song=filename
                        future=pool.submit(lyrics_download.fetch,audio,metadata,seconds)
                        notice=None
                    else:notice='Auto Lyrics · Artist/title/duration required'
                if missing and auto:
                    if future is not None and future_song==filename:value=('Searching lyrics…','','')
                    elif notice:value=(notice,'','')
                candidates=(filename,choices(audio) if audio else [])
                if candidates!=last_choices:
                    last_choices=candidates;self.candidates_changed.emit(candidates)
                if value!=last:
                    last=value;self.changed.emit(value)
                for _ in range(4):
                    if self.isInterruptionRequested():return
                    self.msleep(50)
        finally:
            pool.shutdown(wait=False,cancel_futures=True)

class LyricsPanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('lyricsPanel')
        layout=QVBoxLayout(self);layout.setContentsMargins(10,10,10,10)
        self.auto=QCheckBox('Auto Lyrics')
        self._auto_help='Look up missing lyrics on LRCLIB using title, artist and duration; no audio upload'
        self.auto.setToolTip(self._auto_help)
        self.auto.setChecked(lyrics_download.enabled())
        self.auto.toggled.connect(self.set_auto)
        layout.addWidget(self.auto)
        self.current=QLabel('');self.following=QLabel('')
        for label in (self.current,self.following):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            layout.addWidget(label)
        self.current.setStyleSheet('color: #00ff66; font-size: 24px; font-weight: bold;')
        self.following.setStyleSheet('color: #aaaaaa; font-size: 17px;')
        self.choice_panel=QWidget()
        choice_layout=QVBoxLayout(self.choice_panel);choice_layout.setContentsMargins(0,0,0,0)
        self.choice=QComboBox()
        self.choice.setMinimumContentsLength(12)
        self.choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.choice.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.choice.setAccessibleName('Candidate lyrics version')
        self.try_button=QPushButton('Try & Remember')
        self.choice.currentIndexChanged.connect(self.refresh_choice_button)
        self.try_button.clicked.connect(self.try_choice)
        choice_layout.addWidget(self.choice);choice_layout.addWidget(self.try_button)
        layout.addWidget(self.choice_panel);self.choice_panel.hide()
        self._choice_audio=None
        self.current.setAccessibleName('Current lyric')
        self.following.setAccessibleName('Next lyric')
        self.worker=LyricsWorker(self)
        self.worker.changed.connect(self.display)
        self.worker.candidates_changed.connect(self.show_choices)
        self.worker.start()
    def show_choices(self,value):
        audio,rows=value;self._choice_audio=audio
        self.choice.blockSignals(True);self.choice.clear()
        for row in rows:
            kind='Synced' if row.get('has_synced') else 'Text only'
            self.choice.addItem(f"{row.get('artistName','?')} · {row.get('duration','?')}s · {kind}",row)
            self.choice.setItemData(self.choice.count()-1,str(row.get('albumName','')),Qt.ItemDataRole.ToolTipRole)
        self.choice.blockSignals(False)
        self.choice_panel.setVisible(bool(rows))
        self.refresh_choice_button()
    def refresh_choice_button(self):
        row=self.choice.currentData() or {}
        self.try_button.setText('Try & Remember' if row.get('has_synced') else 'Save Text (No Timing)')
        self.try_button.setEnabled(bool(row))
    def try_choice(self):
        row=self.choice.currentData()
        if not row or not self._choice_audio:return
        if not lyrics_download.enabled():
            self.set_status('Enable Auto Lyrics to download');return
        self.worker.manual=(self._choice_audio,row['id'])
        self.set_status('Downloading selected version…')
        self.try_button.setEnabled(False)
    def set_auto(self,value):
        try:lyrics_download.set_enabled(value)
        except OSError:
            self.auto.blockSignals(True)
            self.auto.setChecked(lyrics_download.enabled())
            self.auto.blockSignals(False)
            self.set_status('Could not save Auto Lyrics preference')
    def set_status(self,text):
        text=text[:160]
        self.auto.setToolTip(self._auto_help+'\n'+text)
        self.auto.setAccessibleDescription(text)
    def display(self,value):
        heading,current,following=value
        self.set_status(heading)
        self.current.setText(current[:1200])
        self.following.setText(following[:1200])
    def shutdown(self):
        self.worker.requestInterruption()
        self.worker.wait()  # IPC uses socket timeouts; never destroy a running QThread.
