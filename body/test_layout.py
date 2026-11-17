"""Headless geometry smoke test; no live control socket or media playback."""
import ast
import tempfile
import shutil
from unittest.mock import patch
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6 import QtCore,QtGui,QtNetwork,QtMultimedia,QtMultimediaWidgets,QtWidgets
import player

class LocalServer(QtNetwork.QLocalServer):
    def listen(self,*args):return True  # Never bind/unlink the live player's socket.

env=dict(vars(player))
for module in (QtCore,QtGui,QtNetwork,QtMultimedia,QtMultimediaWidgets,QtWidgets):
    env.update({name:getattr(module,name) for name in dir(module) if name.startswith('Q')})
env['Qt']=QtCore.Qt
env['QLocalServer']=LocalServer
env['actions']=player.load_actions()
temporary=tempfile.TemporaryDirectory()
env['ROOT']=Path(temporary.name)/'body'
env['ROOT'].mkdir()
shutil.copy2(player.ROOT.parent/'Reference.webp',Path(temporary.name)/'Reference.webp')
from preview import Frames
camera_start=patch.object(Frames,'start')
camera_start.start()  # Geometry tests must not capture camera frames.
from lyrics_panel import LyricsWorker
lyrics_start=patch.object(LyricsWorker,'start')
lyrics_start.start()  # No live music IPC polling during geometry tests.
from llm_dashboard import MetricsWorker
metrics_start=patch.object(MetricsWorker,'start')
metrics_start.start()  # No hardware/server probing in geometry tests.
source=ast.parse(Path(player.__file__).read_text())
main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
body_class=next(n for n in main.body if isinstance(n,ast.ClassDef) and n.name=='Body')
exec(compile(ast.Module(body=[body_class],type_ignores=[]),'layout-test','exec'),env)
Body=env['Body']
real_play_action=Body.play_action
Body.play_action=lambda self,name:setattr(self,'current',name)
app=QtWidgets.QApplication([])
with patch.object(Body, 'refresh_model_catalog', lambda self: None):
    body=Body()
assert body.model_button.parent().objectName() == 'AI Model'
assert body.control_tabs.count() == 4
assert [body.control_tabs.tabText(i) for i in range(4)] == ['AI Model', 'Speech & Audio', 'Camera & Gestures', 'Music']
assert body.control_tabs.widget(3).isAncestorOf(body.playlist_selector)
assert not body.music_panel.isAncestorOf(body.playlist_selector)
assert set(body.playlist_buttons) == {'toggle', 'play'}
assert body.control_tabs.widget(3).isAncestorOf(body.playlist_browse)
with patch.object(QtWidgets.QFileDialog, 'getOpenFileNames', return_value=([str(Path.home()/'Music'/'fixture.mp3'), '/tmp/outside.mp3'], '')) as dialog, patch('playlist.change', return_value='added') as save, patch.object(body, 'refresh_playlist'):
    body.add_music_files()
    save.assert_called_once_with((Path.home()/'Music'/'fixture.mp3').resolve(), add=True)
    assert dialog.call_args.args[2] == str(Path.home()/'Music')
    assert 'Added 1' in body.status.text() and 'Failed 1' in body.status.text()
with patch.object(QtWidgets.QFileDialog, 'getOpenFileNames', return_value=([], '')), patch('playlist.change') as save:
    body.add_music_files()
    save.assert_not_called()
import music
with patch.object(music, 'loaded_track', return_value='/fixture/song.mp3'):
    original_snapshot = body.playlist_snapshot
    body.playlist_snapshot = []
    body.refresh_playlist_toggle()
    assert body.playlist_buttons['toggle'].text() == 'Add to Playlist'
    body.playlist_snapshot = ['/fixture/song.mp3']
    body.refresh_playlist_toggle()
    assert body.playlist_buttons['toggle'].text() == 'Remove from Playlist'
    body.playlist_snapshot = original_snapshot
assert body.control_tabs.widget(3).isAncestorOf(body.music_mode_button)
body.toggle_music_panel()
assert body.music_panel_open and body.content_tabs.isTabVisible(1)
body.toggle_music_panel()
assert not body.music_panel_open and not body.content_tabs.isTabVisible(1)
controls_layout = body.controls_panel.layout()
assert controls_layout.indexOf(body.music_panel) < controls_layout.indexOf(body.content_tabs), 'Music controls must be above shared conversation/lyrics'
assert body.content_tabs.widget(0) is body.chat
assert body.content_tabs.widget(1) is body.lyrics_panel
assert not body.content_tabs.isTabVisible(1)
for left, right in ((body.model_button, body.model_refresh),
                    (body.mic_button, body.voice_button),
                    (body.speech_selector, body.asr_selector),
                    (body.preview_button, body.boxes_button),
                    (body.gesture_control, body.hand_status)):
    grid = left.parent().layout()
    lpos = grid.getItemPosition(grid.indexOf(left))
    rpos = grid.getItemPosition(grid.indexOf(right))
    assert lpos[0] == rpos[0] and lpos[1] == 0 and rpos[1] == 1
assert body.model_selector.parent().layout().getItemPosition(
    body.model_selector.parent().layout().indexOf(body.model_selector)) == (1, 0, 1, 2)
assert body.mic_button.parent() is body.voice_button.parent() is body.speech_selector.parent() is body.asr_selector.parent()
assert body.preview_button.parent() is body.boxes_button.parent() is body.gesture_control.parent()
assert not any(b.text() in ('Local Model', 'Cloud Model') for b in body.findChildren(QtWidgets.QPushButton))
with patch.object(Body, 'model_router') as router:
    router.return_value.current.return_value = ('online', 'test', 'cloud-test')
    body.refresh_model()
    assert body.model_button.text() == 'Model: Cloud'
    with patch.object(body, 'change_model') as change:
        body.model_button.click()
        change.assert_called_once_with('local')
    router.return_value.current.return_value = ('local', 'test', 'local-test')
    body.refresh_model()
    assert body.model_button.text() == 'Model: Local'
    with patch.object(body, 'change_model') as change:
        body.model_button.click()
        change.assert_called_once_with('online')
with patch.object(Body, 'model_router') as router, patch('llm_metrics.provider_mode', side_effect=lambda provider: 'Local' if provider == 'neris-a' else 'Cloud'):
    router.return_value.current.return_value = ('local', 'neris-a', 'google/gemma-4-12b-qat')
    body.model_catalog = [('neris-a', 'qwen/qwen3.5-9b'), ('openai-codex', 'gpt-5.4')]
    body.model_catalog_key = None
    body.refresh_model()
    assert body.model_selector.count() == 2
    with patch.object(body, 'start_model_switch') as switch:
        body.select_model(1)
        switch.assert_called_once_with('local', ('neris-a', 'qwen/qwen3.5-9b'))
    router.return_value.current.return_value = ('online', 'openai-codex', 'gpt-5.4')
    body.refresh_model()
    assert body.model_selector.count() == 1
print('PASS grouped controls, Local/Cloud toggle and filtered model selection (mocked)')
from llm_dashboard import render
body.control_status.setText('Replay · Restarted')
body.beat_status.setText('Beat sync: 120.0 BPM · 1.00× · estimated')
body.repeat_status.setText('Repeat One: On')
body.llm_metrics_label.display(render({'mode':'Local','provider':'test','model':'example/model'},
    {},'Reachable','System RAM: 10/32 GiB\nSystem GPU: 10% | VRAM: 9/16 GiB'))
assert 'Beat sync: 120.0 BPM' in body.music_info_label._full_text
assert 'Repeat One: On' in body.music_info_label.toolTip()
assert 'Replay · Restarted' in body.music_info_label._full_text
assert body.music_info_label._full_text.splitlines() == [
    'Beat sync: 120.0 BPM · 1.00× · estimated', 'Repeat One: On', 'Replay · Restarted']
assert 'Beat sync:' not in body.llm_metrics_label._full_text
assert body.music_info_label.isHidden(), 'Idle header must hide the entire music row'
assert body.state_frame.layout().getItemPosition(body.state_frame.layout().indexOf(body.music_info_label))==(0,2,2,1), 'Music belongs in the rightmost column'
assert not any(label.text().startswith('Beat sync:') for label in body.controls_panel.findChildren(QtWidgets.QLabel)), 'Beat status must not be duplicated below header'
action_labels={name.replace('_',' ').title() for name in env['actions']}
assert not action_labels.intersection({button.text() for button in body.findChildren(QtWidgets.QPushButton)}), 'Manual action buttons must be absent'
for width,height in [(1280,900),(800,700)]:
    body.resize(width,height);body.show();app.processEvents()
    assert body.stack.height()==body.splitter.height(), 'Character does not span full content height'
    assert body.stack.x()<body.right_column.x(), 'Character must be left of controls'
    assert body.state_banner.geometry().right() < body.llm_metrics_label.x(), 'Metrics must be right of name/state'
    assert body.state_frame.height()<230, 'Status frame is wasting vertical space'
    assert 'example/model' in body.llm_metrics_label.toolTip()
    for kind in (QtWidgets.QPushButton,QtWidgets.QComboBox,QtWidgets.QLineEdit,QtWidgets.QSlider,QtWidgets.QPlainTextEdit):
        for widget in body.findChildren(kind):
            assert body.right_column.isAncestorOf(widget),f'{kind.__name__} outside right panel'
    assert body.controls_panel.minimumSizeHint().width()<=body.controls_scroll.viewport().width(), 'Controls clipped horizontally'
    print('PASS layout',body.width(),body.height(),'character',body.stack.size().toTuple(),
          'controls',body.controls_scroll.size().toTuple())
import music
for paused in (False,True):
    with patch.object(music,'volume',return_value=50),patch.object(music,'request',return_value={'data':paused}),patch.object(music,'repeat_one',return_value=False),patch.object(body,'sync_dance'):
        body.refresh_music();app.processEvents()
        assert not body.music_info_label.isHidden()
        assert not body.music_panel.isHidden()
        assert body.content_tabs.isAncestorOf(body.lyrics_panel)
        assert not body.music_panel.isAncestorOf(body.lyrics_panel)
        assert body.content_tabs.isTabVisible(1)
        assert body.lyrics_panel.isVisible()
        assert body.music_info_label.x()>body.llm_metrics_label.geometry().right()
        assert body.music_info_label.x()>body.state_banner.geometry().right()
        assert body.music_info_label.y()==body.llm_metrics_label.y()
        assert body.state_frame.height()<230
with patch.object(music,'volume',return_value=None):
    body.refresh_music();assert body.music_info_label.isHidden()
    assert body.music_panel.isHidden()
    assert not body.lyrics_panel.isVisible()
    assert body.content_tabs.currentWidget() is body.chat
    assert not body.content_tabs.isTabVisible(1)
body.toggle_music_panel()
with patch.object(music, 'volume', return_value=None):
    body.refresh_music()
assert body.music_panel_open and not body.music_panel.isHidden(), 'Manual music mode must remain open without playback'
body.toggle_music_panel()
assert body.music_panel.isHidden()
print('PASS shared conversation/lyrics tabs, automatic music mode and manual idle open/close')
properties = {'path': '/fixture/song.mp3', 'duration': 240.0, 'time-pos': 60.0}
with patch.object(music, 'request', side_effect=lambda args: {'data': properties.get(args[-1])}):
    body.refresh_music_progress(music, True)
assert body.seek_slider.isEnabled() and body.seek_slider.value() == 250
assert body.music_position.text() == '1:00 / 4:00'
body.seek_slider.setSliderDown(True)
properties['time-pos'] = 80.0
with patch.object(music, 'request', side_effect=lambda args: {'data': properties.get(args[-1])}):
    body.refresh_music_progress(music, True)
assert body.seek_slider.value() == 250, 'Poll must not override drag'
body.preview_music_seek(500)
assert body.music_position.text() == '2:00 / 4:00'
body.seek_slider.setSliderDown(False)
with patch.object(music, 'request', return_value={'data': '/fixture/song.mp3'}) as request, patch.object(body, 'refresh_music'):
    body.seek_music(500)
    request.assert_any_call(['seek', 120.0, 'absolute+exact'])
    assert not any(call.args[0][:2] == ['set_property', 'pause'] for call in request.call_args_list)
with patch.object(music, 'request', return_value={'data': '/fixture/other.mp3'}) as request, patch.object(body, 'refresh_music'):
    body.seek_music(500)
    assert request.call_count == 1, 'Track switch must cancel stale seek'
body.refresh_music_progress(music, False)
assert not body.seek_slider.isEnabled() and body.music_position.text() == '0:00 / —'
assert body.music_time(3661) == '1:01:01'
print('PASS seek progress/time, drag stability, absolute seek, pause preservation and track-switch guard')
body.lyrics_panel.display(('Lyrics','Test lyric line','Next lyric line'))
assert body.lyrics_panel.current.text()=='Test lyric line'
assert not hasattr(body.lyrics_panel, 'heading'), 'Redundant Lyrics heading must not occupy a row'
assert body.lyrics_panel.layout().itemAt(1).widget() is body.lyrics_panel.current
assert 'Lyrics' in body.lyrics_panel.auto.toolTip()
assert body.right_column.isAncestorOf(body.lyrics_panel)
body.lyrics_panel.display(('Lyrics unavailable','',''))
assert not body.lyrics_panel.current.text()
body.lyrics_panel.show_choices(('fixture.wav',[{'id':1,'artistName':'Other singer','duration':100,'has_synced':False}]))
assert not body.lyrics_panel.choice_panel.isHidden()
assert 'No Timing' in body.lyrics_panel.try_button.text()
body.lyrics_panel.show_choices((None,[]));assert body.lyrics_panel.choice_panel.isHidden()
print('PASS embedded lyrics panel, current/next labels, candidate choice and unavailable reset')
body.set_camera_preview(True);app.processEvents()
assert not body.camera_panel.isHidden()
assert body.camera_panel.parentWidget() is body.right_column
assert body.camera_panel.y()<body.controls_scroll.y(), 'Camera must be above the controls'
assert body.state_banner.y() < body.camera_panel.y(), 'State banner must be at upper right above camera'
assert body.state_frame.parentWidget() is body.right_column
assert body.state_frame.isAncestorOf(body.state_banner)
assert body.state_frame.isAncestorOf(body.llm_metrics_label)
assert '#000000' in body.state_banner.styleSheet() and '#00ff66' in body.state_banner.styleSheet()
assert body.stack.height()==body.splitter.height()
body.showMaximized();app.processEvents()
assert body.isMaximized()
assert body.stack.height()==body.splitter.height()
print('PASS upper-right preview and maximized window')
body.showNormal()
for width, height in ((1280, 900), (800, 700)):
    body.resize(width, height)
    body.music_panel.show()
    app.processEvents()
    body.controls_scroll.verticalScrollBar().setValue(body.controls_scroll.verticalScrollBar().maximum())
    app.processEvents()
    assert body.control_dock.parentWidget() is body.right_column
    assert not body.controls_scroll.isAncestorOf(body.control_dock)
    for button in (body.model_button, body.model_refresh, body.mic_button,
                   body.voice_button, body.preview_button, body.boxes_button, body.gesture_control):
        page_index = body.control_tabs.indexOf(button.parentWidget())
        assert page_index >= 0
        body.control_tabs.setCurrentIndex(page_index)
        app.processEvents()
        position = button.mapTo(body.right_column, QtCore.QPoint(0, 0))
        assert button.isVisible()
        assert position.y() >= 0 and position.y() + button.height() <= body.right_column.height(), 'Fixed buttons pushed outside window'
    assert body.controls_scroll.height() >= 60, 'Conversation viewport squeezed away'
print('PASS camera + music open: fixed controls visible at 1280/800, independent of content scroll')
body.set_camera_preview(False);app.processEvents()
assert body.camera_panel.isHidden()
assert 'Add' in body.preview_button.text()
assert not body.state_banner.isHidden(), 'State banner must remain visible without camera'
print('PASS embedded preview add/remove without changing full-height character')
Body.play_action=real_play_action
clock=[1000.]
body.sleep_policy.clock=lambda:clock[0]
body.sleep_policy.last_activity=clock[0]
body.music_mode=None
body.current='idle'
with patch.object(body.player,'play'),patch.object(body.player,'setSource'):
    clock[0]=1299.;body.check_sleep();assert not body.sleep_policy.sleeping
    clock[0]=1300.;body.check_sleep();assert body.current=='sleep' and body.sleep_policy.sleeping
    assert body.state_banner.text() == 'Neris-A\nSLEEPING'
    for noisy_state in ('listening','thinking','idle'):
        body.play_action(noisy_state);assert body.current=='sleep'
    body.mark_activity();assert body.current=='idle' and not body.sleep_policy.sleeping
assert body.state_banner.text() == 'Neris-A\nIDLE'
from transition_flow import EDGES
for file in EDGES.values():
    stub=env['ROOT']/file;stub.parent.mkdir(parents=True,exist_ok=True);stub.touch()
for state in ('listening','thinking','speaking'):
    shutil.copy2(player.ROOT/f'assets/{state}_v3_hold.png',env['ROOT']/f'assets/{state}_v3_hold.png')
with patch.object(body.player,'play'),patch.object(body.player,'setSource'):
    for state in ('listening','thinking','speaking'):
        body.play_action(state);assert body.flow.active is not None
        body.media_status(QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia)
        assert body.current==state and body.flow.active is None
        assert body.stack.currentWidget() is body.image and not body.image.pixmap().isNull()
    body.play_action('idle');assert body.flow.active[:2]==('speaking','idle')
    body.media_status(QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia)
    assert body.current=='idle' and body.stack.currentWidget() is body.video
    body.play_action('vulcan_salute');assert body.special_playing
    body.play_action('idle');assert body.current=='vulcan_salute'
    body.media_status(QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia)
    assert body.current=='idle' and not body.special_playing
print('PASS Qt transition endpoint holds, speaking return and uninterrupted Vulcan lifecycle')
for state in ('listening','thinking','speaking','vulcan_salute'):
    body.current=state;body.refresh_state_banner()
    assert body.state_banner.text().startswith('Neris-A\n')
    assert state.replace('_',' ').upper() in body.state_banner.text()
body.current='dancing';body.music_mode='paused';body.refresh_state_banner()
assert 'DANCING (PAUSED)' in body.state_banner.text()
print('PASS upper-right green/black name/state banner, camera-independent, live states and paused music')
print('PASS Qt five-minute sleep transition, noisy states ignored, interaction wake')
body.close()
camera_start.stop()
lyrics_start.stop()
metrics_start.stop()
temporary.cleanup()
