"""Deterministic short feedback through the existing voice-output policy."""
import json
import os
import socket
PREFIX='__neris_music_feedback__:'
PHRASES={
 'playlist_added':{'zh':'已加入音樂清單。','en':'Added to the playlist.','nan':'已經加入音樂清單。'},
 'playlist_removed':{'zh':'已從音樂清單移除。','en':'Removed from the playlist.','nan':'已經對音樂清單移除。'},
 'playlist_exists':{'zh':'這首歌已在清單中。','en':'This song is already in the playlist.','nan':'這首歌已經佇清單內。'},
 'playlist_absent':{'zh':'這首歌不在清單中。','en':'This song is not in the playlist.','nan':'這首歌無佇清單內。'},
 'playlist_failed':{'zh':'音樂清單更新失敗。','en':'Could not update the playlist.','nan':'音樂清單更新失敗。'},
 'replay':{'zh':'收到，已從頭重播。','en':'Got it. Restarted the song.','nan':'收著，已經對頭閣播。'},
 'repeat_on':{'zh':'收到，已開啟單曲循環。','en':'Got it. Repeat one is on.','nan':'收著，這首會閣播。'},
 'repeat_off':{'zh':'收到，已關閉單曲循環。','en':'Got it. Repeat one is off.','nan':'收著，這首袂閣一直重播。'},
 'replay_failed':{'zh':'收到重播指令，但播放器尚未確認成功。','en':'Replay received, but the player did not confirm success.','nan':'收著閣播的指令，毋過播放器猶未確認成功。'},
 'repeat_failed':{'zh':'收到循環指令，但播放器尚未確認成功。','en':'Repeat command received, but the player did not confirm success.','nan':'收著循環的指令，毋過播放器猶未確認成功。'},
}

def phrase(key,language):
    return PHRASES.get(key,{}).get(language)

def enqueue(key):
    if key not in PHRASES:return False
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.5)
            client.connect(f'/run/user/{os.getuid()}/neris-stage2-voice.sock')
            client.sendall((json.dumps({'text':PREFIX+key})+'\n').encode())
            return json.loads(client.recv(4096)).get('ok') is True
    except (OSError,ValueError):return False
