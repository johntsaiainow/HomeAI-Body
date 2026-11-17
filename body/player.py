"""Stage-two standalone body player. Never imports stage-one code."""
import argparse
import json
from history import save, recent
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import MUSIC_DIR

ROOT = Path(__file__).resolve().parent


def load_actions(path=ROOT / 'actions.json'):
    with Path(path).open(encoding='utf-8') as stream:
        actions = json.load(stream)
    if not isinstance(actions, dict) or 'idle' not in actions:
        raise ValueError('Action index must contain idle')
    for name, entry in actions.items():
        if not isinstance(entry, dict):
            raise ValueError(f'Invalid action: {name}')
        if entry.get('file') is not None and not isinstance(entry['file'], str):
            raise ValueError(f'Invalid file: {name}')
    return actions


def resolve_asset(actions, name, base=ROOT):
    entry = actions.get(name, {})
    filename = entry.get('file')
    if not filename:
        return None
    path = Path(filename).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve() if path.is_file() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Validate index without Qt')
    args = parser.parse_args()
    actions = load_actions()
    if args.check:
        for name in actions:
            print(f'{name}: {resolve_asset(actions, name) or "reference image fallback"}')
        return

    from PySide6.QtCore import Qt, QUrl, QTimer, QEvent
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtGui import QPixmap, QPalette, QColor
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    from PySide6.QtWidgets import (QApplication, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                                    QStackedWidget, QVBoxLayout, QWidget, QPlainTextEdit, QLineEdit, QSlider, QComboBox, QScrollArea, QSplitter)

    class Body(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('Neris-A · Stage 2')
            self.resize(1180, 850)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
            self.current = 'idle'
            from idle_sleep import IdleSleep
            self.sleep_policy = IdleSleep(timeout=300)
            from transition_flow import TransitionFlow
            self.flow = TransitionFlow()
            self.special_playing = False
            self.after_special = 'idle'
            self.music_mode = None
            from beat_sync import Analyzer
            self.beat_analyzer = Analyzer()
            self.beat_aligned = False
            self.reference = QPixmap(str(ROOT.parent / 'Reference.webp'))
            self.still = self.reference
            self.image = QLabel()
            self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.video = QVideoWidget()
            self.stack = QStackedWidget()
            self.stack.addWidget(self.image)
            self.stack.addWidget(self.video)
            # Use identical letterbox colors for still images and video surfaces.
            for surface in (self.stack, self.image, self.video):
                palette = surface.palette()
                palette.setColor(QPalette.ColorRole.Window, QColor('black'))
                palette.setColor(QPalette.ColorRole.Base, QColor('black'))
                surface.setPalette(palette)
                surface.setAutoFillBackground(True)
                surface.setStyleSheet('background-color: black;')
            self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            self.status = QLabel()
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.audio.setMuted(True)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.player.mediaStatusChanged.connect(self.media_status)
            self.player.errorOccurred.connect(self.media_error)
            # Full-height character on the left; every control lives on the right.
            root_layout = QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            self.splitter = QSplitter(Qt.Orientation.Horizontal)
            self.splitter.setChildrenCollapsible(False)
            self.stack.setMinimumWidth(200)
            self.splitter.addWidget(self.stack)
            self.controls_panel = QWidget()
            self.controls_panel.setObjectName('controlsPanel')
            layout = QVBoxLayout(self.controls_panel)
            layout.setContentsMargins(12, 12, 12, 12)
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            self.controls_scroll = QScrollArea()
            self.controls_scroll.setWidgetResizable(True)
            self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.controls_scroll.setMinimumWidth(340)
            self.controls_scroll.setWidget(self.controls_panel)
            self.right_column = QWidget()
            right_layout = QVBoxLayout(self.right_column)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(0)
            self.state_frame = QWidget()
            self.state_frame.setObjectName('characterStatusFrame')
            self.state_frame.setStyleSheet('QWidget#characterStatusFrame { background: #000000; }')
            state_layout = QGridLayout(self.state_frame)
            state_layout.setContentsMargins(0, 0, 0, 0)
            state_layout.setSpacing(0)
            self.state_banner = QLabel('Neris-A\nIDLE')
            self.state_banner.setObjectName('characterStateBanner')
            self.state_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.state_banner.setWordWrap(True)
            self.state_banner.setMinimumHeight(110)
            self.state_banner.setStyleSheet(
                'QLabel { background-color: #000000; color: #00ff66; '
                'font-size: 28px; font-weight: bold; padding: 8px; }')
            state_layout.addWidget(self.state_banner, 0, 0, 2, 1)
            from llm_dashboard import MetricsLabel, DashboardField, MusicInfoLabel
            self.llm_metrics_label = MetricsLabel()
            state_layout.addWidget(self.llm_metrics_label, 0, 1, 2, 1)
            state_layout.setColumnStretch(0, 2)
            state_layout.setColumnStretch(1, 3)
            self.music_info_label = MusicInfoLabel()
            self.control_status = DashboardField(self.music_info_label, 'control', 'Control: Ready')
            state_layout.addWidget(self.music_info_label, 0, 2, 2, 1)
            state_layout.setColumnStretch(2, 0)
            right_layout.addWidget(self.state_frame)
            from camera_panel import CameraPanel
            self.camera_panel = CameraPanel()
            self.camera_panel.hide_requested.connect(lambda: self.set_camera_preview(False))
            right_layout.addWidget(self.camera_panel)
            right_layout.addWidget(self.controls_scroll, 1)
            self.control_dock = QWidget()
            self.control_dock.setObjectName('fixedControlDock')
            self.dock_layout = QVBoxLayout(self.control_dock)
            self.dock_layout.setContentsMargins(6, 2, 6, 4)
            self.dock_layout.setSpacing(2)
            right_layout.addWidget(self.control_dock)
            self.splitter.addWidget(self.right_column)
            self.splitter.setStretchFactor(0, 2)
            self.splitter.setStretchFactor(1, 1)
            self.splitter.setSizes([650, 530])
            self.splitter.splitterMoved.connect(lambda *_: self.update_image())
            root_layout.addWidget(self.splitter)
            self.chat = QPlainTextEdit()
            self.chat.setReadOnly(True)
            self.chat.setPlaceholderText('Your conversation will appear here')
            self.chat.setMaximumBlockCount(1000)
            self.chat.setMinimumHeight(160)
            self.chat.setMaximumHeight(320)
            from PySide6.QtWidgets import QTabWidget
            self.content_tabs = QTabWidget()
            self.content_tabs.setMinimumHeight(180)
            self.content_tabs.addTab(self.chat, 'Conversation')
            layout.addWidget(self.content_tabs, 1)
            try:
                for record in recent():
                    label = 'You' if record['role'] == 'user' else 'Neris-A'
                    self.chat.appendPlainText(f"{label}：{record['text']}\n")
            except OSError as error:
                self.chat.appendPlainText(f'Could not load history: {error}')
            prompt_row = QHBoxLayout()
            self.prompt = QLineEdit()
            self.prompt.setPlaceholderText('Command Prompt: type a message or music request')
            self.prompt.setMaxLength(2000)
            self.prompt.returnPressed.connect(self.submit_prompt)
            send_button = QPushButton('Send')
            send_button.clicked.connect(self.submit_prompt)
            prompt_row.addWidget(self.prompt, 1)
            prompt_row.addWidget(send_button)
            layout.addLayout(prompt_row)
            from PySide6.QtWidgets import QGroupBox
            self.control_tabs = QTabWidget()
            self.control_tabs.setDocumentMode(True)
            self.dock_layout.addWidget(self.control_tabs)
            def control_group(title):
                group = QGroupBox()
                group.setObjectName(title)
                group_layout = QGridLayout(group)
                group_layout.setContentsMargins(6, 6, 6, 6)
                group_layout.setHorizontalSpacing(6)
                group_layout.setVerticalSpacing(4)
                group_layout.setColumnStretch(0, 1)
                group_layout.setColumnStretch(1, 1)
                self.control_tabs.addTab(group, title)
                return group_layout
            model_layout = control_group('AI Model')
            speech_layout = control_group('Speech & Audio')
            preview_row = control_group('Camera & Gestures')
            music_tools = control_group('Music')
            self.music_mode_button = QPushButton('Music Mode: Open')
            self.music_mode_button.clicked.connect(self.toggle_music_panel)
            music_tools.addWidget(self.music_mode_button, 0, 0)
            self.music_panel_open = False
            self.preview_button = QPushButton('Camera Preview: Add')
            self.preview_button.setCheckable(True)
            self.preview_button.setToolTip('Add or remove the upper-right preview; camera perception stays active')
            self.preview_button.clicked.connect(self.set_camera_preview)
            preview_row.addWidget(self.preview_button, 0, 0)
            self.mic_button = QPushButton('Microphone: On')
            self.mic_button.clicked.connect(self.toggle_microphone)
            speech_layout.addWidget(self.mic_button, 0, 0)
            self.voice_button = QPushButton('Voice Output: On')
            self.voice_button.clicked.connect(self.toggle_voice_output)
            speech_layout.addWidget(self.voice_button, 0, 1)
            self.model_button = QPushButton('Model: Unknown')
            self.model_button.clicked.connect(self.toggle_model)
            model_layout.addWidget(self.model_button, 0, 0)
            self.model_selector = QComboBox()
            self.model_selector.setMinimumWidth(0)
            self.model_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.model_selector.setMinimumContentsLength(12)
            self.model_selector.setToolTip('Choose provider / model for the current mode; availability not tested')
            self.model_selector.activated.connect(self.select_model)
            model_layout.addWidget(self.model_selector, 1, 0, 1, 2)
            self.model_catalog = []
            self.model_catalog_key = None
            self.model_refresh = QPushButton('Refresh Model List')
            self.model_refresh.clicked.connect(self.refresh_model_catalog)
            model_layout.addWidget(self.model_refresh, 0, 1)
            from PySide6.QtCore import QProcess
            self.model_switch_process = QProcess(self)
            self.model_switch_process.finished.connect(self.model_switch_finished)
            self.model_switch_process.errorOccurred.connect(self.model_switch_failed)
            self.model_process = QProcess(self)
            self.model_process.setWorkingDirectory(str(Path(__file__).resolve().parent.parent))
            self.model_process.finished.connect(self.model_catalog_finished)
            self.model_process.errorOccurred.connect(self.model_catalog_failed)
            self.model_catalog_timeout = QTimer(self)
            self.model_catalog_timeout.setSingleShot(True)
            self.model_catalog_timeout.timeout.connect(self.model_process.kill)
            self.refresh_model_catalog()
            self.model_timer = QTimer(self)
            self.model_timer.timeout.connect(self.refresh_model)
            self.model_timer.start(1000)
            self.refresh_model()
            from speech_service import selected
            self.speech_selector = QComboBox()
            self.speech_selector.addItem('Mandarin · ASR + Voice', 'zh')
            self.speech_selector.addItem('English · ASR + Voice', 'en')
            self.speech_selector.addItem('Taigi · ASR + Voice (CPU / Experimental)', 'nan')
            self.speech_selector.setCurrentIndex(max(0, self.speech_selector.findData(selected())))
            self.speech_selector.currentIndexChanged.connect(self.change_speech_service)
            self.speech_selector.setMinimumWidth(0)
            self.speech_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.speech_selector.setMinimumContentsLength(8)
            speech_layout.addWidget(self.speech_selector, 1, 0)
            self.asr_selector = QComboBox()
            self.asr_selector.addItem('ASR Engine: Auto', 'auto')
            self.asr_selector.addItem('ASR Engine: Vosk (streaming)', 'vosk')
            self.asr_selector.addItem('ASR Engine: Whisper', 'whisper')
            self.asr_selector.currentIndexChanged.connect(self.change_asr_engine)
            self.asr_selector.setMinimumWidth(0)
            self.asr_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.asr_selector.setMinimumContentsLength(8)
            speech_layout.addWidget(self.asr_selector, 1, 1)
            self.mic_timer = QTimer(self)
            self.mic_timer.timeout.connect(self.refresh_microphone)
            self.mic_timer.start(300)
            self.refresh_microphone()
            self.boxes_button = QPushButton('Detection Boxes: On')
            self.boxes_button.setCheckable(True)
            self.boxes_button.setChecked(True)
            self.boxes_button.clicked.connect(self.toggle_boxes)
            preview_row.addWidget(self.boxes_button, 0, 1)
            self.gesture_control = QPushButton('Gesture Control: On')
            self.gesture_control.setCheckable(True)
            enabled = True
            try:
                enabled = json.loads((ROOT / 'gesture-music.json').read_text()).get('enabled', True) is True
            except (OSError, ValueError, AttributeError):
                pass
            self.gesture_control.setChecked(enabled)
            self.gesture_control.setText('Gesture Control: On' if enabled else 'Gesture Control: Off')
            self.gesture_control.clicked.connect(self.toggle_gesture_control)
            preview_row.addWidget(self.gesture_control, 1, 0)
            self.hand_status = QLabel('Hands: waiting for detector…')
            self.hand_status.setWordWrap(True)
            self.hand_status.setMinimumWidth(0)
            preview_row.addWidget(self.hand_status, 1, 1)
            self.hand_timer = QTimer(self)
            self.hand_timer.timeout.connect(self.refresh_hands)
            self.hand_timer.start(500)
            self.boxes_timer = QTimer(self)
            self.boxes_timer.timeout.connect(self.sync_boxes)
            self.boxes_timer.start(300)
            self.sync_boxes()
            self.music_panel = QGroupBox('Music')
            music_layout = QVBoxLayout(self.music_panel)
            music_layout.setContentsMargins(0, 0, 0, 0)
            music_row = QHBoxLayout()
            music_layout.addLayout(music_row)
            from PySide6.QtWidgets import QStyle
            for icon, tooltip, command in [
                    (QStyle.StandardPixmap.SP_MediaSeekBackward, 'Rewind 10 seconds', ['seek', -10, 'relative']),
                    (QStyle.StandardPixmap.SP_MediaPause, 'Pause', ['set_property', 'pause', True]),
                    (QStyle.StandardPixmap.SP_MediaPlay, 'Play / Resume', ['set_property', 'pause', False]),
                    (QStyle.StandardPixmap.SP_MediaSeekForward, 'Forward 10 seconds', ['seek', 10, 'relative']),
                    (QStyle.StandardPixmap.SP_MediaStop, 'Stop', ['quit'])]:
                button = QPushButton()
                button.setIcon(self.style().standardIcon(icon))
                button.setToolTip(tooltip)
                button.setAccessibleName(tooltip)
                button.clicked.connect(lambda checked=False, c=command: self.music_command(c))
                music_row.addWidget(button)
            progress_row = QHBoxLayout()
            music_layout.addLayout(progress_row)
            self.music_position = QLabel('0:00 / —')
            self.seek_slider = QSlider(Qt.Orientation.Horizontal)
            self.seek_slider.setRange(0, 1000)
            self.seek_slider.setMinimumWidth(60)
            self.seek_slider.setTracking(False)
            self.seek_slider.setEnabled(False)
            self.seek_slider.setAccessibleName('Music playback position')
            self.seek_slider.setToolTip('Drag to seek; release to apply')
            self.seek_duration = 0.0
            self.seek_path = None
            self.seek_slider.sliderMoved.connect(self.preview_music_seek)
            self.seek_slider.valueChanged.connect(self.seek_music)
            progress_row.addWidget(self.seek_slider, 1)
            progress_row.addWidget(self.music_position)
            volume_row = QHBoxLayout()
            music_layout.addLayout(volume_row)
            self.volume_label = QLabel('Volume: —')
            volume_row.addWidget(self.volume_label)
            self.volume_slider = QSlider(Qt.Orientation.Horizontal)
            self.volume_slider.setRange(0, 100)
            self.volume_slider.setMinimumWidth(100)
            self.volume_slider.setAccessibleName('Music volume')
            self.volume_slider.setToolTip('Music volume: 0–100%')
            self.volume_slider.setTracking(False)
            self.volume_slider.valueChanged.connect(self.set_music_volume)
            volume_row.addWidget(self.volume_slider, 1)
            playlist_row = QHBoxLayout()
            music_tools.addLayout(playlist_row, 1, 0, 1, 2)
            self.playlist_selector = QComboBox()
            self.playlist_selector.setMinimumWidth(0)
            self.playlist_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.playlist_selector.setMinimumContentsLength(8)
            self.playlist_selector.setAccessibleName('Saved playlist')
            playlist_row.addWidget(self.playlist_selector, 1)
            self.playlist_buttons = {}
            for key, label in (('toggle', 'Add to Playlist'), ('play', '▶')):
                button = QPushButton(label)
                button.setToolTip({'toggle':'Add/remove current song; with no loaded song, remove selected saved song',
                                   'play':'Play selected saved song'}[key])
                button.clicked.connect(lambda checked=False, key=key: self.playlist_command(key))
                playlist_row.addWidget(button)
                self.playlist_buttons[key] = button
            self.playlist_browse = QPushButton('Add Music Files…')
            self.playlist_browse.setToolTip('Choose local audio files from ~/Music to add to the saved playlist')
            self.playlist_browse.clicked.connect(self.add_music_files)
            music_tools.addWidget(self.playlist_browse, 0, 1)
            self.playlist_snapshot = None
            self.playlist_selector.currentIndexChanged.connect(self.refresh_playlist_toggle)
            self.refresh_playlist()
            self.repeat_status = DashboardField(self.music_info_label, 'repeat', 'Repeat One: Off')
            layout.insertWidget(layout.indexOf(self.content_tabs), self.music_panel)
            from lyrics_panel import LyricsPanel
            self.lyrics_panel = LyricsPanel()
            self.content_tabs.addTab(self.lyrics_panel, 'Lyrics')
            self.content_tabs.setTabVisible(1, False)
            self.content_music_active = False
            self.beat_status = DashboardField(self.music_info_label, 'beat', 'Beat sync: waiting for music')
            self.music_panel.hide()
            self.music_timer = QTimer(self)
            self.music_timer.timeout.connect(self.refresh_music)
            self.music_timer.start(1000)
            try:
                preview_enabled = json.loads((ROOT / 'camera-panel.json').read_text()).get('enabled', False) is True
            except (OSError, ValueError, AttributeError):
                preview_enabled = False
            self.set_camera_preview(preview_enabled)
            self.sleep_timer = QTimer(self)
            self.sleep_timer.timeout.connect(self.check_sleep)
            self.sleep_timer.start(1000)
            QApplication.instance().installEventFilter(self)
            self.play_action('idle')
            self.server = QLocalServer(self)
            self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
            self.server.newConnection.connect(self.accept_connection)
            # Do not remove a socket belonging to an existing player.
            if not self.server.listen(str(ROOT / 'control.sock')):
                raise RuntimeError('Could not start control server. Check for another running player. ' + self.server.errorString())
            self.connections = {}

        def refresh_state_banner(self):
            label = {'sleep': 'SLEEPING', 'vulcan_salute': 'VULCAN SALUTE'}.get(
                self.current, self.current.replace('_', ' ').upper())
            if self.current == 'dancing' and self.music_mode == 'paused':
                label += ' (PAUSED)'
            self.state_banner.setText(f'Neris-A\n{label}')

        def mark_activity(self):
            if self.sleep_policy.touch():
                self.play_action('idle')

        def check_sleep(self):
            if self.sleep_policy.poll(music_playing=self.music_mode == 'playing',
                                      speaking=self.current == 'speaking'):
                self.play_action('sleep')

        def eventFilter(self, watched, event):
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress,
                                QEvent.Type.Wheel, QEvent.Type.TouchBegin):
                if watched is self or (isinstance(watched, QWidget) and self.isAncestorOf(watched)):
                    self.mark_activity()
            return super().eventFilter(watched, event)

        def set_camera_preview(self, enabled=None):
            if enabled is None:
                enabled = not self.camera_panel.wanted
            self.camera_panel.set_enabled(enabled)
            self.preview_button.setChecked(bool(enabled))
            self.preview_button.setText('Camera Preview: Remove' if enabled else 'Camera Preview: Add')
            try:
                temporary = ROOT / 'camera-panel.tmp'
                temporary.write_text(json.dumps({'enabled': bool(enabled)}))
                temporary.replace(ROOT / 'camera-panel.json')
            except OSError as error:
                self.status.setText(f'Could not save preview setting: {error}')

        def model_router(self):
            import sys
            project = str(Path(__file__).resolve().parent.parent)
            if project not in sys.path:
                sys.path.insert(0, project)
            import model_router
            return model_router

        def refresh_model(self):
            try:
                mode, provider, model = self.model_router().current()
                label = {'local': 'Local', 'online': 'Cloud'}.get(mode, mode)
                target = 'Local' if mode == 'online' else 'Cloud'
                self.model_button.setText(f'Model: {label}')
                self.model_button.setToolTip(f'{provider} / {model}\nClick to switch to {target}; next AI request')
                key = (mode, provider, model, tuple(self.model_catalog))
                if key != self.model_catalog_key:
                    from llm_metrics import provider_mode
                    choices = [(provider, model)]
                    for entry in self.model_catalog:
                        if (provider_mode(entry[0]) == ('Cloud' if mode == 'online' else 'Local')
                                and entry not in choices):
                            choices.append(entry)
                    self.model_selector.clear()
                    for entry in choices:
                        self.model_selector.addItem(' / '.join(entry), entry)
                    self.model_selector.setCurrentIndex(0)
                    self.model_catalog_key = key
            except (OSError, ValueError, KeyError):
                self.model_button.setText('Model: Unknown')
                self.model_button.setToolTip('Model configuration unavailable')

        def refresh_model_catalog(self):
            if self.model_process.state().value != 0:
                return
            self.model_refresh.setEnabled(False)
            self.model_refresh.setText('Loading Models…')
            import os, shutil
            from PySide6.QtCore import QProcessEnvironment
            environment = QProcessEnvironment.systemEnvironment()
            # Desktop launchers do not inherit interactive shell PATH additions.
            paths = [str(Path.home() / '.local/npm/bin'), str(Path.home() / '.local/bin'),
                     environment.value('PATH', os.defpath)]
            search_path = os.pathsep.join(paths)
            environment.insert('PATH', search_path)
            self.model_process.setProcessEnvironment(environment)
            executable = shutil.which('pi', path=search_path)
            if not executable:
                self.model_catalog_failed()
                self.status.setText('Model list unavailable: Pi executable not found')
                return
            self.model_process.start(executable, ['--offline', '--list-models'])
            self.model_catalog_timeout.start(15000)

        def model_catalog_failed(self, *args):
            self.model_catalog_timeout.stop()
            self.model_refresh.setEnabled(True)
            self.model_refresh.setText('Refresh Model List')
            self.model_selector.setToolTip('Could not read Pi model catalog; saved selection retained')
            if args:
                self.status.setText('Model list unavailable: ' + self.model_process.errorString())

        def model_catalog_finished(self, code, *args):
            self.model_catalog_failed()
            if code != 0:
                self.status.setText('Model list command failed; saved selection retained')
                return
            output = bytes(self.model_process.readAllStandardOutput()).decode('utf-8', errors='replace')
            rows = [line.split() for line in output.splitlines()]
            header = next((i for i, row in enumerate(rows) if row[:2] == ['provider', 'model']), None)
            if header is None:
                self.status.setText('Model list format not recognized; saved selection retained')
                return
            self.model_catalog = list(dict.fromkeys(tuple(row[:2]) for row in rows[header + 1:] if len(row) >= 6))
            self.model_selector.setToolTip('Pi catalog only; credentials, server and model availability not tested')
            self.status.setText(f'Model catalog loaded: {len(self.model_catalog)} entries')
            self.refresh_model()

        def select_model(self, index):
            entry = self.model_selector.itemData(index)
            if not entry:
                return
            try:
                mode, _, _ = self.model_router().current()
                self.start_model_switch('online' if mode == 'online' else 'local', entry)
            except (OSError, ValueError, KeyError) as error:
                self.status.setText(f'Model selection failed ({type(error).__name__})')
            self.model_catalog_key = None
            self.refresh_model()

        def toggle_model(self):
            try:
                mode, _, _ = self.model_router().current()
                self.change_model('local' if mode == 'online' else 'online')
            except (OSError, ValueError, KeyError) as error:
                self.status.setText(f'Model selection failed ({type(error).__name__})')
                self.refresh_model()

        def change_model(self, mode):
            self.start_model_switch(mode)

        def start_model_switch(self, mode, entry=None):
            import sys
            if self.model_switch_process.state().value != 0:
                self.status.setText('Model switch already in progress')
                return
            for widget in (self.model_button, self.model_selector):widget.setEnabled(False)
            self.status.setText('Switching model: unloading old local model before loading the new one…')
            arguments = ['-B', str(Path(__file__).resolve().parents[1] / 'model_router.py')]
            arguments += ['--select', mode, *entry] if entry else [mode]
            self.model_switch_process.start(sys.executable, arguments)

        def model_switch_failed(self, *args):
            for widget in (self.model_button, self.model_selector):widget.setEnabled(True)
            self.status.setText('Model switch process failed; check local model service')
            self.refresh_model()

        def model_switch_finished(self, code, *args):
            for widget in (self.model_button, self.model_selector):widget.setEnabled(True)
            try:
                result = json.loads(bytes(self.model_switch_process.readAllStandardOutput()).decode())
                if code != 0 or not result.get('ok'):
                    self.status.setText('Model switch failed: ' + str(result.get('error', 'unknown error')))
                else:
                    self.status.setText('Model switch complete — next AI request; cloud access not tested')
            except (ValueError, TypeError):
                self.status.setText('Model switch failed; no confirmation received')
            self.model_catalog_key = None
            self.refresh_model()

        def change_speech_service(self, index):
            import speech_service
            try:
                language = self.speech_selector.itemData(index)
                speech_service.select(language)
                if language == 'nan':
                    self.status.setText('Taigi ASR + local CPU voice enabled; new sentences may synthesize slowly')
                else:
                    self.status.setText('Speech service changed — applies to the next utterance')
            except (OSError, ValueError) as error:
                self.status.setText(f'Could not switch speech service: {error}')
            self.refresh_microphone()

        def change_asr_engine(self, index):
            import speech_service
            try:
                speech_service.set_backend(speech_service.selected(), self.asr_selector.itemData(index))
                self.status.setText('ASR engine changed — applies to the next utterance; voice output unchanged')
            except (OSError, ValueError) as error:
                self.status.setText(f'Could not change ASR engine: {error}')
            self.refresh_microphone()

        def refresh_microphone(self):
            import speech_service
            language = speech_service.selected()
            self.asr_selector.blockSignals(True)
            self.asr_selector.setItemText(0, 'ASR Engine: Auto (Breeze ASR26)' if language == 'nan' else 'ASR Engine: Auto (prefer Vosk)')
            self.asr_selector.setItemText(2, 'ASR Engine: Whisper (English tiny)' if language == 'en' else 'ASR Engine: Whisper-family (Breeze ASR26)')
            for i in range(self.asr_selector.count()):
                self.asr_selector.model().item(i).setEnabled(speech_service.ready(language, self.asr_selector.itemData(i)))
            self.asr_selector.setCurrentIndex(self.asr_selector.findData(speech_service.backend(language)))
            self.asr_selector.blockSignals(False)
            index = self.speech_selector.findData(speech_service.selected())
            if index >= 0 and index != self.speech_selector.currentIndex():
                self.speech_selector.blockSignals(True)
                self.speech_selector.setCurrentIndex(index)
                self.speech_selector.blockSignals(False)
            import microphone
            self.mic_button.setText('Microphone: Off' if microphone.muted() else 'Microphone: On')
            self.mic_button.setToolTip('Toggle Neris microphone capture; not system-wide hardware mute')
            import voice_output
            self.voice_button.setText('Voice Output: On' if voice_output.enabled() else 'Voice Output: Off')
            self.voice_button.setToolTip('Toggle spoken replies only; microphone and music are unaffected')

        def toggle_voice_output(self):
            import voice_output
            if not voice_output.toggle():
                self.status.setText('Could not change voice output setting')
            self.refresh_microphone()

        def toggle_microphone(self):
            import microphone
            if not microphone.toggle():
                self.status.setText('Could not change microphone setting')
            self.refresh_microphone()

        def toggle_gesture_control(self, enabled):
            try:
                temporary = ROOT / 'gesture-music.tmp'
                temporary.write_text(json.dumps({'enabled': enabled}))
                temporary.replace(ROOT / 'gesture-music.json')
                self.gesture_control.setText('Gesture Control: On' if enabled else 'Gesture Control: Off')
            except OSError as error:
                self.gesture_control.setChecked(not enabled)
                self.status.setText(f'Could not update gesture control: {error}')

        def refresh_hands(self):
            from datetime import datetime
            try:
                data = json.loads((ROOT / 'gesture-status.json').read_text())
                age = (datetime.now().astimezone() - datetime.fromisoformat(data['time'])).total_seconds()
                if age > 5:
                    self.hand_status.setText('Hands: detector data is stale')
                    return
                candidates = ', '.join(f"{c['name']} {c['score']:.0%}" for c in data['candidates'])
                rules = ', '.join(data.get('rule_candidates', []))
                if rules:
                    candidates = f'{rules} (rule)' + (f' / {candidates}' if candidates else '')
                if data['hands']:
                    self.last_hand_text = f"Hands: {data['hands']} · {candidates or 'Unclassified'} (candidate, not confirmed)"
                    self.last_hand_time = datetime.now().timestamp()
                if datetime.now().timestamp() - getattr(self, 'last_hand_time', 0) < 4:
                    self.hand_status.setText(self.last_hand_text)
                else:
                    self.hand_status.setText('Hands: 0 · Show your whole hand to the camera')
            except (OSError, ValueError, KeyError):
                self.hand_status.setText('Hands: detector not ready')

        def sync_boxes(self):
            try:
                enabled = json.loads((ROOT / 'detection-boxes.json').read_text()).get('enabled', True)
                if not isinstance(enabled, bool):
                    return
                self.boxes_button.setChecked(enabled)
                self.boxes_button.setText('Detection Boxes: On' if enabled else 'Detection Boxes: Off')
            except (OSError, ValueError, AttributeError):
                pass

        def toggle_boxes(self, enabled):
            try:
                temporary = ROOT / 'detection-boxes.main.tmp'
                temporary.write_text(json.dumps({'enabled': enabled}))
                temporary.replace(ROOT / 'detection-boxes.json')
                self.sync_boxes()
            except OSError as error:
                self.status.setText(f'Could not change detection boxes: {error}')

        def refresh_music(self):
            import music
            value = music.volume()
            pause = music.request(['get_property', 'pause']) if value is not None else None
            if pause is not None:
                mode = 'paused' if pause.get('data') else 'playing'
                previous = self.music_mode
                self.music_mode = mode
                if mode == 'playing':
                    self.mark_activity()
                if self.current not in ('dancing', 'vulcan_salute', 'sleep'):
                    self.play_action('dancing')
                elif self.current == 'dancing' and mode != previous:
                    if mode == 'paused':
                        self.player.pause()
                    else:
                        self.player.play()
                if self.current == 'dancing':
                    self.status.setText('dancing · paused' if mode == 'paused' else 'dancing · music playing')
                    self.sync_dance(music)
            elif value is None and self.music_mode is not None:
                self.music_mode = None
                self.beat_analyzer.select(None)
                self.beat_aligned = False
                self.player.setPlaybackRate(1.0)
                self.beat_status.setText('Beat sync: waiting for music')
                self.play_action('idle')
            self.refresh_playlist()
            self.refresh_music_progress(music, value is not None)
            self.refresh_state_banner()
            active = self.music_mode in ('playing', 'paused')
            if active != self.content_music_active:
                self.set_music_panel_open(active)
                self.content_music_active = active
            self.music_info_label.setVisible(self.music_mode in ('playing', 'paused'))
            self.state_frame.layout().setColumnStretch(2, 3 if active else 0)
            if value is None:self.repeat_status.setText('Repeat One: — (no song)')
            if value is not None:
                looping = music.repeat_one()
                self.repeat_status.setText('Repeat One: ' + ('Unknown' if looping is None else 'On' if looping else 'Off'))
                self.volume_label.setText(f'Volume: {value:.0f}%')
                if not self.volume_slider.isSliderDown():
                    self.volume_slider.blockSignals(True)
                    self.volume_slider.setValue(max(0, min(100, round(value))))
                    self.volume_slider.blockSignals(False)

        def sync_dance(self, music):
            from beat_sync import phase
            try:
                settings = json.loads((ROOT / 'dance-timing.json').read_text())
                if not settings.get('enabled', True):
                    self.player.setPlaybackRate(1.0)
                    self.beat_status.setText('Beat sync: Off')
                    self.beat_aligned = False
                    return
                reply = music.request(['get_property', 'path'])
                path = reply.get('data') if reply else None
                if path != self.beat_analyzer.path:
                    self.beat_aligned = False
                self.beat_analyzer.select(path)
                data = self.beat_analyzer.result
                if not data:
                    self.player.setPlaybackRate(1.0)
                    self.beat_status.setText('Beat sync: unavailable' if self.beat_analyzer.error else 'Beat sync: analyzing song…')
                    return
                reply = music.request(['get_property', 'time-pos'])
                position = reply.get('data') if reply else None
                duration = self.player.duration() / 1000
                beats = float(settings.get('beats_per_cycle', 16))
                if position is None or duration <= 0 or beats <= 0:
                    return
                rate, target = phase(float(position), data['bpm'], data['offset'] + float(settings.get('offset_seconds', 0)), duration, beats)
                limited = max(float(settings.get('min_rate', .75)), min(float(settings.get('max_rate', 1.35)), rate))
                self.player.setPlaybackRate(limited)
                clamped = abs(limited - rate) > .001
                error = abs(self.player.position() / 1000 - target)
                error = min(error, duration - error) if error <= duration else error
                if not clamped and (not self.beat_aligned or error > .25):
                    self.player.setPosition(round(target * 1000))
                    self.beat_aligned = True
                label = 'estimated / uncalibrated' if not settings.get('calibrated') else 'calibrated video timing'
                self.beat_status.setText(f"Beat sync: {data['bpm']:.1f} BPM · {limited:.2f}× · {label}" + (' · speed limited, not phase locked' if clamped else ''))
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.beat_status.setText(f'Beat sync: unavailable ({error})')

        def set_music_panel_open(self, opened):
            self.music_panel_open = bool(opened)
            self.music_panel.setVisible(self.music_panel_open)
            self.content_tabs.setTabVisible(1, self.music_panel_open)
            self.content_tabs.setCurrentIndex(1 if self.music_panel_open else 0)
            self.music_mode_button.setText('Music Mode: Close' if self.music_panel_open else 'Music Mode: Open')

        def toggle_music_panel(self):
            self.set_music_panel_open(not self.music_panel_open)

        def refresh_playlist(self):
            import playlist
            try:
                rows = playlist.tracks()
                if rows != self.playlist_snapshot:
                    selected = self.playlist_selector.currentData()
                    self.playlist_selector.clear()
                    for path in rows:
                        self.playlist_selector.addItem(Path(path).stem, path)
                        self.playlist_selector.setItemData(self.playlist_selector.count()-1, path, Qt.ItemDataRole.ToolTipRole)
                    index = self.playlist_selector.findData(selected)
                    if index >= 0:self.playlist_selector.setCurrentIndex(index)
                    self.playlist_snapshot = rows
                self.playlist_selector.setPlaceholderText('Saved playlist (empty)')
                self.playlist_buttons['play'].setEnabled(bool(rows))
                self.refresh_playlist_toggle()
            except (OSError, ValueError, TypeError):
                self.status.setText('Could not read saved playlist')

        def add_music_files(self):
            from PySide6.QtWidgets import QFileDialog
            import playlist
            filenames, _ = QFileDialog.getOpenFileNames(
                self, 'Add Music Files', str(MUSIC_DIR),
                'Audio files (*.mp3 *.flac *.wav *.m4a *.ogg *.opus *.aac);;All files (*)')
            if not filenames:
                return
            added = existing = failed = 0
            root = MUSIC_DIR.resolve()
            for filename in filenames:
                try:
                    path = Path(filename).resolve()
                    if not path.is_relative_to(root):
                        raise ValueError('Choose audio files inside ~/Music')
                    result = playlist.change(path, add=True)
                    added += result == 'added'
                    existing += result == 'exists'
                except (OSError, ValueError, TypeError):
                    failed += 1
            self.refresh_playlist()
            self.status.setText(f'Playlist · Added {added} · Already saved {existing} · Failed {failed}')

        def refresh_playlist_toggle(self, *args):
            import music
            track = music.loaded_track() or self.playlist_selector.currentData()
            rows = self.playlist_snapshot or []
            present = bool(track and str(Path(track).expanduser().resolve()) in rows)
            button = self.playlist_buttons['toggle']
            button.setText('Remove from Playlist' if present else 'Add to Playlist')
            button.setEnabled(bool(track))
            button.setToolTip(('Remove: ' if present else 'Add: ') + (Path(track).name if track else 'No song loaded'))

        def playlist_command(self, action):
            import playlist, music
            try:
                track = ((music.loaded_track() or self.playlist_selector.currentData())
                         if action == 'toggle' else self.playlist_selector.currentData())
                if not track:
                    self.status.setText('No song selected or loaded')
                    return
                if action == 'play':
                    if not Path(track).is_file():raise ValueError('Saved file is missing')
                    music.play(track)
                    self.status.setText('Playlist · Playback requested')
                else:
                    present = str(Path(track).expanduser().resolve()) in playlist.tracks()
                    result = playlist.change(track, add=not present)
                    self.status.setText('Playlist · '+result)
                self.refresh_playlist()
            except (OSError, ValueError, TypeError) as error:
                self.status.setText(f'Playlist failed ({type(error).__name__})')

        @staticmethod
        def music_time(seconds):
            seconds = max(0, int(seconds))
            hours, rest = divmod(seconds, 3600)
            minutes, seconds = divmod(rest, 60)
            return f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes}:{seconds:02d}'

        def refresh_music_progress(self, music, online):
            import math
            def property_value(name):
                reply = music.request(['get_property', name]) if online else None
                return reply.get('data') if reply else None
            path = property_value('path')
            duration = property_value('duration')
            position = property_value('time-pos')
            valid = (isinstance(path, str) and isinstance(duration, (int, float))
                     and math.isfinite(duration) and duration > 0
                     and isinstance(position, (int, float)) and math.isfinite(position))
            if self.seek_slider.isSliderDown():
                # Keep the captured track/duration until release; seek_music checks
                # the live path so a track switch cannot seek the wrong song.
                return
            self.seek_path = path if valid else None
            self.seek_duration = float(duration) if valid else 0.0
            self.seek_slider.setEnabled(valid)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(round(max(0, min(1, position / duration)) * 1000) if valid else 0)
            self.seek_slider.blockSignals(False)
            self.music_position.setText(f'{self.music_time(position)} / {self.music_time(duration)}' if valid else '0:00 / —')

        def preview_music_seek(self, value):
            if self.seek_duration > 0:
                self.music_position.setText(f'{self.music_time(value / 1000 * self.seek_duration)} / {self.music_time(self.seek_duration)}')

        def seek_music(self, value):
            import music
            if self.seek_duration <= 0 or not self.seek_path:
                return
            reply = music.request(['get_property', 'path'])
            if not reply or reply.get('data') != self.seek_path:
                self.status.setText('Track changed — seek cancelled')
            else:
                target = max(0, min(self.seek_duration, value / 1000 * self.seek_duration))
                if music.request(['seek', target, 'absolute+exact']) is None:
                    self.status.setText('Could not seek music')
            self.refresh_music()

        def set_music_volume(self, value):
            import music
            if music.request(['set_property', 'volume', value]) is None:
                self.status.setText('Could not change music volume')
            self.refresh_music()

        def music_command(self, command):
            import music
            if not music.command(command):
                self.status.setText('Music control failed. Check that the player is running.')
            self.refresh_music()

        def submit_prompt(self):
            text = self.prompt.text().strip()
            if text and self.send_text(text):
                self.prompt.clear()

        def send_text(self, text):
            import socket
            import os
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(0.3)
                    client.connect(f'/run/user/{os.getuid()}/neris-stage2-voice.sock')
                    client.sendall((json.dumps({'text': text}) + '\n').encode())
                    response = bytearray()
                    while b'\n' not in response:
                        chunk = client.recv(4096)
                        if not chunk or len(response) > 4096:
                            raise ValueError('Invalid response')
                        response.extend(chunk)
                    reply = json.loads(response.split(b'\n', 1)[0])
                    if not reply.get('ok'):
                        raise ValueError(reply.get('error', 'Rejected'))
                self.status.setText('Command queued')
                return True
            except (OSError, ValueError) as error:
                self.status.setText(f'Could not send; input preserved: {error}')
                return False

        def stop_music(self):
            import music
            stopped = music.stop()
            self.status.setText('Stop requested' if stopped else 'No music is playing')

        def accept_connection(self):
            while self.server.hasPendingConnections():
                client = self.server.nextPendingConnection()
                self.connections[client] = bytearray()
                client.readyRead.connect(lambda c=client: self.read_command(c))
                client.disconnected.connect(lambda c=client: self.drop_connection(c))

        def drop_connection(self, client):
            self.connections.pop(client, None)
            client.deleteLater()

        def read_command(self, client):
            buffer = self.connections[client]
            buffer.extend(bytes(client.readAll()))
            if len(buffer) > 65536:
                client.abort()
                return
            if b'\n' not in buffer:
                return
            line = bytes(buffer).split(b'\n', 1)[0]
            try:
                command = json.loads(line)
                if not isinstance(command, dict):
                    raise ValueError('Expected JSON object')
                if command.get('type') == 'activity':
                    self.mark_activity()
                    result = {'ok': True, 'type': 'activity', 'sleeping': False}
                elif command.get('type') == 'body_state':
                    result = {'ok': True, 'action': self.current,
                              'desired_action': self.flow.desired,
                              'transition': self.flow.active,
                              'special_playing': self.special_playing,
                              'holding_image': self.stack.currentWidget() == self.image,
                              'media_source': self.player.source().toLocalFile(),
                              'media_error': self.player.errorString(),
                              'llm_dashboard': self.llm_metrics_label._full_text,
                              'model_catalog_count': len(self.model_catalog),
                              'model_choices_count': self.model_selector.count(),
                              'music_dashboard': self.music_info_label._full_text,
                              'music_info_visible': not self.music_info_label.isHidden()}
                elif command.get('type') == 'sleep_state':
                    result = {'ok': True, 'sleeping': self.sleep_policy.sleeping,
                              'idle_seconds': round(self.sleep_policy.clock() - self.sleep_policy.last_activity, 1),
                              'timeout_seconds': self.sleep_policy.timeout, 'action': self.current}
                elif command.get('type') == 'camera_preview':
                    mode = command.get('mode', 'toggle')
                    if mode not in ('toggle', 'open', 'close', 'status'):
                        raise ValueError('Invalid preview mode')
                    if mode != 'status':
                        self.mark_activity()
                        self.set_camera_preview(None if mode == 'toggle' else mode == 'open')
                    result = {'ok': True, 'type': 'camera_preview', 'visible': self.camera_panel.wanted,
                              'frames_received': self.camera_panel.frames_received,
                              'error': self.camera_panel.last_error}
                elif command.get('type') == 'control_status':
                    text = command.get('text')
                    if not isinstance(text, str) or len(text)>300:
                        raise ValueError('Invalid control status')
                    self.control_status.setText(text)
                    result = {'ok': True, 'type': 'control_status'}
                elif command.get('type') == 'status':
                    text = command.get('text')
                    if not isinstance(text, str):
                        raise ValueError('Invalid status')
                    self.status.setText(text)
                    result = {'ok': True, 'type': 'status'}
                elif command.get('type') == 'dialogue':
                    role = command.get('role')
                    text = command.get('text')
                    if role not in ('user', 'assistant') or not isinstance(text, str) or not text.strip():
                        raise ValueError('Invalid dialogue')
                    if role == 'user' or not text.startswith('[Observation]'):
                        self.mark_activity()
                    label = 'You' if role == 'user' else 'Neris-A'
                    self.chat.appendPlainText(f'{label}：{text}\n')
                    self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
                    try:
                        if command.get('persisted') is not True:
                            save(role, text)
                        result = {'ok': True, 'type': 'dialogue', 'saved': True}
                    except OSError as error:
                        self.status.setText(f'Could not save conversation: {error}')
                        result = {'ok': True, 'type': 'dialogue', 'saved': False,
                                  'error': str(error)}
                else:
                    name = command.get('action')
                    if not isinstance(name, str) or name not in actions:
                        raise ValueError('Unknown action')
                    if name in ('vulcan_salute', 'dancing'):
                        self.mark_activity()
                    self.play_action(name)
                    result = {'ok': True, 'action': self.current,
                              'requested_action': name,
                              'material': ('image' if actions.get(self.current, {}).get('kind') == 'image' else 'video') if resolve_asset(actions, self.current) else 'reference'}
            except (ValueError, TypeError) as error:
                result = {'ok': False, 'error': str(error)}
            client.write((json.dumps(result) + '\n').encode())
            client.disconnectFromServer()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self.camera_panel.fit_height()
            self.update_image()

        def update_image(self):
            self.image.setPixmap(self.still.scaled(
                max(1, self.stack.width()), max(1, self.stack.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

        def fallback(self, message):
            fallback_image = actions.get(self.current, {}).get('fallback_image')
            path = ROOT / fallback_image if fallback_image else None
            self.still = QPixmap(str(path)) if path and path.is_file() else self.reference
            self.player.stop()
            self.stack.setCurrentWidget(self.image)
            self.update_image()
            self.status.setText(message)

        def play_action(self, name):
            from transition_flow import STATES
            if self.sleep_policy.sleeping and name in STATES:
                return
            if self.music_mode is not None and name not in ('vulcan_salute', 'sleep'):
                name = 'dancing'
            if self.special_playing and name not in ('vulcan_salute', 'sleep'):
                self.after_special = name
                return
            if name == 'vulcan_salute':
                if self.special_playing:
                    return
                self.flow.abort()
                self.special_playing = True
                self.after_special = 'idle'
                self._play_direct(name)
                return
            self.special_playing = False
            if name in STATES:
                edge = self.flow.request(name)
                if edge:
                    self.play_transition(edge)
                elif self.flow.active is None:
                    self.hold_transition_endpoint()
                return
            self.flow.abort()
            self._play_direct(name)

        def play_transition(self, edge):
            path = ROOT / edge[2]
            self.current = edge[1]
            self.refresh_state_banner()
            if not path.is_file():
                self.flow.abort()
                self.fallback(f'Transition missing: {path.name}')
                return
            self.player.stop()
            self.stack.setCurrentWidget(self.video)
            self.status.setText(f'{edge[0]} → {edge[1]} · {path.name}')
            self.player.setPlaybackRate(1.0)
            self.player.setLoops(QMediaPlayer.Loops.Once)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()

        def hold_transition_endpoint(self):
            name = self.flow.node
            if name == 'idle':
                self._play_direct('idle')
                return
            path = ROOT / actions[name]['hold_image']
            self.current = name
            self.refresh_state_banner()
            self.player.stop()
            self.still = QPixmap(str(path))
            self.stack.setCurrentWidget(self.image)
            self.update_image()
            self.status.setText(f'{name.title()} · Holding endpoint')

        def _play_direct(self, name):
            if self.sleep_policy.sleeping and name in ('idle', 'listening', 'thinking', 'speaking'):
                return  # Raw/noisy voice-state updates must not wake the body.
            if name == 'sleep':
                if self.music_mode == 'playing':
                    return
                self.sleep_policy.sleeping = True
            if self.music_mode is not None and name not in ('vulcan_salute', 'sleep'):
                name = 'dancing'
            if (name == self.current
                    and self.stack.currentWidget() == self.video
                    and (self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                         or (self.music_mode == 'paused' and self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState))):
                return
            self.current = name
            self.refresh_state_banner()
            path = resolve_asset(actions, name)
            if path is None:
                # No generation request: missing material is explicitly a fallback.
                self.fallback(f'{name} · No video available; showing reference image')
                return
            self.player.stop()
            if actions.get(name, {}).get('kind') == 'image':
                self.still = QPixmap(str(path))
                self.stack.setCurrentWidget(self.image)
                self.update_image()
                self.status.setText('Sleeping · Interact to wake' if name == 'sleep' else name)
                return
            self.stack.setCurrentWidget(self.video)
            self.status.setText(f'{name} · {path.name}')
            if name != 'dancing':
                self.player.setPlaybackRate(1.0)
            self.player.setLoops(QMediaPlayer.Loops.Infinite if actions.get(name, {}).get('loop', False) else QMediaPlayer.Loops.Once)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()
            if self.music_mode == 'paused' and name == 'dancing':
                self.player.pause()

        def media_status(self, status):
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                if self.flow.active:
                    edge = self.flow.finish()
                    if edge:
                        self.play_transition(edge)
                    else:
                        self.hold_transition_endpoint()
                    return
                if self.special_playing:
                    self.special_playing = False
                    self.flow.abort()
                    self.play_action(self.after_special)
                    return
                if actions.get(self.current, {}).get('loop', False):
                    self.player.setPosition(0)
                    self.player.play()
                else:
                    self.play_action('idle')

        def media_error(self, error, message):
            self.flow.abort()
            self.special_playing = False
            self.fallback(f'Playback failed: {message}')

        def closeEvent(self, event):
            if self.model_switch_process.state().value != 0:
                self.status.setText('Please wait for model unloading/loading to finish before closing')
                event.ignore()
                return
            QApplication.instance().removeEventFilter(self)
            self.sleep_timer.stop()
            self.model_catalog_timeout.stop()
            self.model_process.kill()
            self.model_process.waitForFinished(1000)
            self.lyrics_panel.shutdown()
            self.llm_metrics_label.shutdown()
            self.camera_panel.shutdown()
            self.player.stop()
            for client in list(self.connections):
                client.abort()
            self.server.close()
            super().closeEvent(event)

    app = QApplication([])
    body = Body()
    body.showMaximized()
    def fit_columns():
        body.splitter.setSizes([int(body.width() * 0.55), int(body.width() * 0.45)])
        body.update_image()
    QTimer.singleShot(150, fit_columns)
    app.exec()


if __name__ == '__main__':
    main()
