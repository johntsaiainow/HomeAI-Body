"""Deterministic music transport commands: never let an LLM promise an unexecuted replay."""
from pathlib import Path
import re
import music
import speech_service

REPLAY={'重播','再播一次','再播放一次','重新播放','從頭播放','從頭再播','replay','playagain','restartsong','restartmusic'}

def playlist_command(text):
    compact=re.sub(r'[\s，。！？,.!?]', '', text.casefold())
    start={'播放音樂清單','播放音樂選單','播放音樂單','播放歌單','播放我的清單',
           'playplaylist','playtheplaylist','playmyplaylist','startplaylist'}
    steps={'下一首':1,'下一曲':1,'nextsong':1,'nexttrack':1,
           '上一首':-1,'上一曲':-1,'previoussong':-1,'previoustrack':-1}
    if compact not in start and compact not in steps:return None
    language=speech_service.selected()
    if compact in steps:
        ok=music.playlist_step(steps[compact])
        if language=='en':return 'Changed playlist track.' if ok else 'No next/previous track is available, or the player did not confirm the change.'
        if language=='nan':return '已經換歌。' if ok else '無下一首或上一首，抑是播放器無確認換歌。'
        return '已切換清單歌曲。' if ok else '沒有可切換的下一首／上一首，或播放器未確認切換成功。'
    result=music.play_playlist()
    if result.get('ok'):
        count=result['count'];skipped=result.get('skipped',0)
        if language=='en':return f'Playing {count} saved songs in order. Skipped {skipped} unavailable files.'
        if language=='nan':return f'開始照順序播音樂清單，共 {count} 首，略過 {skipped} 個無法度播放的檔案。'
        return f'已開始依序播放音樂清單，共 {count} 首；略過 {skipped} 個無法播放的檔案。'
    if result.get('reason')=='empty':
        if language=='en':return 'The playlist is empty or all saved files are missing. Add songs in the Music tab first.'
        if language=='nan':return '音樂清單無歌抑是檔案已經無去，請先佇 Music 分頁加歌。'
        return '音樂清單是空的，或歌曲檔案都已失效；請先到 Music 分頁加入歌曲。'
    if language=='en':return 'Playlist playback was not confirmed. Please check the saved list and player.'
    if language=='nan':return '播放器無確認音樂清單開始播放，請檢查清單佮播放器。'
    return '未能確認音樂清單開始播放，請檢查清單與播放器。'


def replay_command(text):
    compact=re.sub(r'[\s，。！？,.!?]','',text.casefold())
    if compact not in REPLAY:return None
    result=music.replay()
    language=speech_service.selected()
    if result.get('ok'):
        name=Path(result['path']).stem
        if language=='en':return f'Restarted {name} from the beginning.'
        if language=='nan':return f'對頭開始閣播 {name}。'
        return f'已從頭重播 {name}。'
    if result.get('reason')=='no_track':
        if language=='en':return 'No previous song is recorded. Please tell me which song to play.'
        if language=='nan':return '目前無會當閣播的歌曲紀錄，請講歌名。'
        return '目前沒有可重播的歌曲紀錄，請說「播放」加歌名。'
    if language=='en':return 'Replay was attempted, but the player did not confirm success.'
    if language=='nan':return '有試欲閣播，毋過播放器猶未確認成功。'
    return '已嘗試重播，但播放器未確認成功，請檢查播放狀態。'
