"""Real mpv IPC fixture; null audio and private socket, never touches live music."""
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import wave
import music
from lyrics import Lyrics
from music_gate import MusicGate

if __name__=='__main__':
    if not shutil.which('mpv'):raise SystemExit('mpv unavailable')
    original=music.IPC
    original_last=music.LAST
    with tempfile.TemporaryDirectory(prefix='neris-lrc-') as directory:
        root=Path(directory);music.IPC=root/'test.sock';music.LAST=root/'music-state.json'
        audio=root/'Fixture.wav'
        with wave.open(str(audio),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000)
            stream.writeframes(b'\x00\x00'*16000*10)
        audio.with_suffix('.lrc').write_text('[00:00.20]First fixture\n[00:01.00]Second fixture\n[00:03.00]Third fixture')
        proc=subprocess.Popen(['mpv','--no-config','--really-quiet','--no-video','--ao=null',
            '--pause=yes','--idle=yes',f'--input-ipc-server={music.IPC}',str(audio)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            engine=Lyrics()
            for _ in range(50):
                path=music.request(['get_property','path'])
                position=music.request(['get_property','time-pos'])
                if path and position and isinstance(position.get('data'),(int,float)):break
                time.sleep(.05)
            assert path and Path(path['data'])==audio
            def snapshot():
                p=music.request(['get_property','path'])
                t=music.request(['get_property','time-pos'])
                return engine.update(p['data'] if p else None,t['data'] if t else None)
            def seek(second,text):
                assert music.request(['seek',second,'absolute+exact'])
                for _ in range(30):
                    value=snapshot()
                    if value[1]==text:return value
                    time.sleep(.05)
                raise AssertionError(value)
            assert seek(2,'Second fixture')[2]=='Third fixture'
            time.sleep(.25);assert snapshot()[1]=='Second fixture'
            assert seek(.5,'First fixture')[2]=='Second fixture'
            assert music.repeat_one() is False
            assert music.toggle_repeat_one() is True
            assert music.repeat_one() is True
            assert music.toggle_repeat_one() is False
            gate=MusicGate()
            assert not gate.blocked(force=True)  # Paused music permits ASR.
            assert music.replay()['ok']
            assert gate.blocked(force=True)  # Replayed music blocks ASR too.
            assert music.request(['get_property','pause'])['data'] is False
            assert music.request(['get_property','time-pos'])['data']<1
            music.request(['quit']);proc.wait(timeout=3)
            assert snapshot()==('Lyrics · No music playing','','')
            assert not gate.blocked(force=True)
            assert music.replay(require_loaded=True)['reason']=='no_track'
            assert music.toggle_repeat_one() is None
            print('PASS real mpv replay+ASR gate playing/paused/stopped, lyrics synchronization; null audio/private socket')
        finally:
            music.IPC=original;music.LAST=original_last
            if proc.poll() is None:proc.terminate();proc.wait(timeout=3)
