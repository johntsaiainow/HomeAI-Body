#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import VOICE_MODELS, MUSIC_DIR, VOICE_DIR
import glob
import json
import re
import time
import random
import subprocess
import threading
import queue
import tempfile
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import opencc
from body_bridge import notify, dialogue
import music
import microphone
import voice_output
import speech_service
import llm_metrics

# Initialize OpenCC converter (s2twp: Simplified to Traditional Chinese with Taiwan idiom conversion)
cc = opencc.OpenCC('s2twp')

# ================= 1. Paths and Configuration =================
MODELS_DIR = str(VOICE_MODELS)
VOSK_MODEL_PATH = os.path.join(MODELS_DIR, "vosk-cn")

PIPER_ZH_MODEL = os.path.join(MODELS_DIR, "zh_TW-huayan-medium.onnx")
PIPER_EN_MODEL = os.path.join(MODELS_DIR, "en_US-lessac-medium.onnx")

MUSIC_DIR = str(MUSIC_DIR)

# 自動尋找 AGENTS.md 所在目錄
GLOBAL_AGENT_DIR = str(Path(__file__).resolve().parents[1])
LOCAL_AGENT_DIR = str(VOICE_DIR)
if os.path.exists(os.path.join(GLOBAL_AGENT_DIR, "AGENTS.md")):
    AGENT_WORK_DIR = GLOBAL_AGENT_DIR
elif os.path.exists(os.path.join(LOCAL_AGENT_DIR, "AGENTS.md")):
    AGENT_WORK_DIR = LOCAL_AGENT_DIR
else:
    AGENT_WORK_DIR = GLOBAL_AGENT_DIR

SAMPLE_RATE = 16000
BLOCK_SIZE = 1600
SILENCE_THRESHOLD = 500  # Audio threshold (adjust based on mic sensitivity)
SILENCE_DURATION = 0.65   # Silence duration in seconds before ending recording

print("Loading offline ASR model (Vosk)...")
if not os.path.exists(VOSK_MODEL_PATH):
    print(f"Error: Vosk model path not found at {VOSK_MODEL_PATH}")
    sys.exit(1)

vosk_model = Model(VOSK_MODEL_PATH)

# Queue for combining voice and text inputs
command_queue = queue.Queue()

# Event flag to pause VAD listening during TTS speech or music playback
is_playing_audio = threading.Event()
is_playing_music = threading.Event()

# ================= 2. Bilingual Piper TTS and Audio Playback =================
def clean_text_for_tts(text):
    """ Clean markdown syntax and code blocks for natural TTS reading """
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # Remove code blocks
    text = re.sub(r'[*_`#\-\+]', ' ', text)                # Replace symbols/hyphens with space
    return re.sub(r'\s+', ' ', text).strip()

def split_zh_en_segments(text):
    """ 將中英文混雜的句子切分為 [(語言, 文字片段), ...] """
    tokens = re.split(r'([A-Za-z0-9]+(?:[\s\.,!\?\'’]+[A-Za-z0-9]+)*)', text)
    segments = []
    for token in tokens:
        part = token.strip()
        if not part:
            continue
        if re.search(r'[A-Za-z]', part) and not re.search(r'[\u4e00-\u9fff]', part):
            segments.append(("en", part))
        else:
            if re.search(r'[\u4e00-\u9fff0-9]', part):
                segments.append(("zh", part))
    return segments

def offline_speak(text, body_action=None, force_english=False, speech_delay=0.0, audio_file=None):
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return

    tts_language = speech_service.selected()
    dialogue('assistant', text)
    if body_action:
        notify(body_action)
    if not voice_output.enabled():
        print(f'Voice output Off; text response: {text}', flush=True)
        if not body_action:
            notify('idle')
        return
    is_playing_audio.set()
    if not body_action:
        notify('thinking')

    cached_audio = bool(audio_file)
    try:
        if speech_delay > 0:
            time.sleep(speech_delay)
        print(f"\n🤖 Agent Response:\n{text}\n")
        segments = [('en', clean_text)] if (force_english or tts_language == 'en') else split_zh_en_segments(clean_text)
        wav_files = [audio_file] if audio_file else []
        if audio_file:
            segments = []  # Reuse actual Taigi synthesis, never Mandarin Piper.
        elif tts_language == 'nan' and not force_english:
            from body_bridge import status
            from taigi_tts_client import synthesize
            status('Synthesizing Taigi voice locally on CPU; this may take a while')
            try:
                wav_files = synthesize(clean_text)
            except Exception as error:
                print(f'Taigi TTS failed: {error}', flush=True)
                status('Taigi voice unavailable — text saved; see tts-taigi/worker.log')
                return
            segments = []
            cached_audio = True
        temp_audio = tempfile.TemporaryDirectory(prefix='neris-stage2-')

        for idx, (lang, seg_text) in enumerate(segments):
            if not voice_output.enabled():
                return
            out_wav = os.path.join(temp_audio.name, f'tts_part_{idx}.wav')
            model_path = PIPER_EN_MODEL if lang == "en" else PIPER_ZH_MODEL

            subprocess.run(
                ["piper", "--model", model_path, "--output_file", out_wav],
                input=seg_text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            wav_files.append(out_wav)

        if wav_files and voice_output.enabled():
            if not body_action:
                notify('speaking')
            player = subprocess.Popen(["mpv", "--no-terminal", "--gapless-audio=yes"] + wav_files)
            try:
                while player.poll() is None:
                    if not voice_output.enabled():
                        player.terminate()
                        break
                    time.sleep(0.1)
                try:
                    player.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    player.kill()
                    player.wait()
            finally:
                if player.poll() is None:
                    player.terminate()
                    player.wait()
            for f in wav_files:
                if not cached_audio and os.path.exists(f):
                    os.remove(f)
    finally:
        if 'temp_audio' in locals():
            temp_audio.cleanup()
        time.sleep(0.4)  # 等待喇叭殘響結束再恢復麥克風監聽
        is_playing_audio.clear()
        if not body_action:
            notify('idle')

def play_audio_file(file_path, blocking=True):
    """ Helper function to play music/audio files while pausing VAD listening """
    if not os.path.exists(file_path):
        print(f"Error: Audio file not found at {file_path}")
        return

    def _play_worker():
        is_playing_music.set()
        notify('idle')
        try:
            print(f"🎵 Playing audio: {file_path}")
            music.play(file_path).wait()
        finally:
            time.sleep(0.4)
            is_playing_music.clear()
            print("🎵 Audio playback finished. VAD resumed.")

    if blocking:
        _play_worker()
    else:
        threading.Thread(target=_play_worker, daemon=True).start()

waiting_song_until = 0


def search_and_play_offline_music(keyword=""):
    global waiting_song_until
    """ 在 ~/music 資料夾（含子目錄）離線搜尋並播放音樂 """
    if not os.path.exists(MUSIC_DIR):
        os.makedirs(MUSIC_DIR, exist_ok=True)
        return f"已為您建立音樂資料夾 {MUSIC_DIR}，請先放入音樂檔案。"

    all_songs = []
    for ext in ("*.mp3", "*.flac", "*.wav", "*.m4a", "*.ogg"):
        all_songs.extend(glob.glob(os.path.join(MUSIC_DIR, "**", ext), recursive=True))

    if not all_songs:
        return "音樂資料夾裡目前沒有任何歌曲。"

    if keyword:
        from song_match import rank
        matched = rank(keyword, all_songs)
        if not matched:
            waiting_song_until = time.monotonic() + 60
            return f'找不到和「{keyword}」接近的歌，請再說一次歌名，或說取消點歌。'
        if len(matched) > 1 and matched[0][0] - matched[1][0] < 0.08:
            waiting_song_until = time.monotonic() + 60
            choices = '、'.join(item[2] for item in matched[:3])
            return f'有幾首接近的歌：{choices}。你想聽哪一首？'
        target_song = matched[0][1]
    else:
        # 沒指定歌名時隨機挑選一首
        target_song = random.choice(all_songs)

    waiting_song_until = 0
    song_name = os.path.splitext(os.path.basename(target_song))[0]
    play_audio_file(target_song, blocking=False)
    return f"好的，為您播放 {song_name}。"

# ================= 3. VAD Streaming Listener (Background Thread) =================
def listen_vad_loop():
    from music_gate import MusicGate
    music_gate = MusicGate()
    from asr_client import BreezeClient
    breeze = BreezeClient()
    import atexit
    atexit.register(breeze.close)
    rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)
    english_vosk_model = None
    english_vosk_path = Path(__file__).resolve().parents[1] / 'models/vosk-model-small-en-us-0.15'

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                            dtype='int16', channels=1) as stream:
        while True:
            speaking = False
            last_speech_time = time.time()
            audio_buffer = []
            voiced_chunks = 0
            language = speech_service.selected()
            english_ready = (english_vosk_path / 'DOWNLOAD_COMPLETE').is_file()
            engine = speech_service.backend(language)
            streaming = engine == 'vosk' or (engine == 'auto' and (language == 'zh' or (language == 'en' and english_ready)))
            if language == 'en' and english_ready and streaming:
                if english_vosk_model is None:
                    english_vosk_model = Model(str(english_vosk_path))
                rec = KaldiRecognizer(english_vosk_model, SAMPLE_RATE)
            else:
                rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            streaming_result = None
            rec.Reset()
            if streaming:
                breeze.close()

            while True:
                selected_language = speech_service.selected()
                if selected_language != language or speech_service.backend(selected_language) != engine:
                    language = selected_language
                    audio_buffer.clear()
                    speaking = False
                    voiced_chunks = 0
                    rec.Reset()
                    notify('idle')
                    break  # Rebuild the selected recognizer at the outer loop.
                if microphone.muted():
                    stream.stop()
                    audio_buffer.clear()
                    speaking = False
                    voiced_chunks = 0
                    rec.Reset()
                    notify('idle')
                    print('Microphone capture paused by user', flush=True)
                    while microphone.muted():
                        time.sleep(0.1)
                    stream.start()
                    print('Microphone capture resumed', flush=True)
                    continue
                data, _ = stream.read(BLOCK_SIZE)
                # RawInputStream returns a CFFI buffer; Vosk requires bytes.
                data = bytes(data)

                if is_playing_audio.is_set() or music_gate.blocked():
                    speaking = False
                    audio_buffer.clear()
                    voiced_chunks = 0
                    rec.Reset()
                    time.sleep(0.05)
                    continue

                audio_chunk = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_chunk.astype(np.float32)).mean()

                if volume > SILENCE_THRESHOLD:
                    if not speaking:
                        notify('listening')
                        print("\n🗣️ Speech detected...")
                        speaking = True
                    last_speech_time = time.time()
                    voiced_chunks += 1
                    audio_buffer.append(data)
                elif speaking:
                    audio_buffer.append(data)
                    if time.time() - last_speech_time > SILENCE_DURATION:
                        print("✅ Speech finished, processing...")
                        break
                # Feed Vosk incrementally, not a batch after the silence delay.
                if streaming and speaking and rec.AcceptWaveform(data):
                    streaming_result = json.loads(rec.Result())
                    break
                if len(audio_buffer) * BLOCK_SIZE >= SAMPLE_RATE * 29:
                    break

            if audio_buffer:
                full_audio = b''.join(audio_buffer)
                if voiced_chunks * BLOCK_SIZE < SAMPLE_RATE * 0.5:
                    print('ASR: discarded short/noisy segment', flush=True)
                    notify('idle')
                    continue
                if microphone.muted() or is_playing_audio.is_set() or music_gate.blocked(force=True):
                    notify('idle')
                    continue
                try:
                    notify('thinking')
                    asr_started = time.monotonic()
                    if streaming:
                        result = streaming_result if streaming_result is not None else json.loads(rec.FinalResult())
                    else:
                        result = breeze.transcribe(full_audio, language)
                    print(f'ASR round trip: {time.monotonic()-asr_started:.3f}s; audio: {len(full_audio)/(2*SAMPLE_RATE):.2f}s', flush=True)
                    print(f'ASR backend {"Vosk streaming (" + language + ")" if streaming else "Whisper English" if language == "en" else "Breeze ASR26"}: {result}', flush=True)
                except Exception as error:
                    print(f'ASR backend unavailable ({language}): {error}', flush=True)
                    from body_bridge import status
                    status('Selected ASR unavailable — check logs or choose another ASR engine')
                    rec.Reset()
                    notify('idle')
                    continue
                if microphone.muted() or is_playing_audio.is_set() or music_gate.blocked(force=True):
                    notify('idle')
                    continue
                if speech_service.selected() != language or speech_service.backend(language) != engine:
                    notify('idle')
                    continue
                raw_text = result.get("text", "").strip()
                if language != 'en':
                    raw_text = raw_text.replace(' ', '')
                if len(raw_text) >= 2:  # 過濾單字環境雜訊
                    text = cc.convert(raw_text)
                    print(f"🗣 Recognition result: '{text}'")
                    notify('thinking')
                    command_queue.put(text)
                else:
                    notify('idle')

# ================= 4. Keyboard Input Loop (Background Thread) =================
def keyboard_input_loop():
    while True:
        try:
            user_input = input("\n⌨️  Prompt > ").strip()
            if user_input:
                # 支援在播歌時直接於鍵盤輸入 stop 中斷音樂
                if user_input.lower() in ("stop", "停止", "停止播放"):
                    music.stop()
                    print("⏹️ Music stopped.")
                    continue
                command_queue.put(user_input)
        except (EOFError, KeyboardInterrupt):
            break

# ================= 5. Interface with Pi CLI Tool =================
preview_process = None


def localized(zh, en):
    return en if speech_service.selected() == 'en' else zh


import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_router

def process_pi_agent_command(user_text):
    global preview_process, waiting_song_until
    if not user_text:
        return None

    if user_text == '__neris_toggle_preview__':
        from body_bridge import send
        sent = send({'type': 'camera_preview', 'mode': 'toggle'})
        return localized('已送出切換右上方攝影機預覽的要求。', 'Camera preview toggle requested.') if sent else localized('身體介面未連線，無法切換預覽。', 'The interface is disconnected; camera preview cannot be changed.')
    if user_text == '__neris_choose_music__':
        waiting_song_until = time.monotonic() + 60
        return localized('你想聽哪首歌？請說歌名，或說取消點歌。', 'What song would you like to hear? Say its title, or say cancel.')
    dialogue('user', user_text)
    notify('thinking')
    text_lower = user_text.lower()
    model_reply = model_router.handle_command(user_text, english=speech_service.selected() == 'en')
    if model_reply is not None:
        waiting_song_until = 0
        return model_reply
    from music_commands import replay_command, playlist_command
    playlist_reply = playlist_command(user_text)
    if playlist_reply is not None:
        waiting_song_until = 0
        return playlist_reply
    replay_reply = replay_command(user_text)
    if replay_reply is not None:
        waiting_song_until = 0
        return replay_reply

    compact = re.sub(r'[\s，。！？,.!?]', '', text_lower)
    language_commands = {'切換華語':'zh', '切換中文':'zh', '切換國語':'zh',
                         '切換英文':'en', '切換英語':'en', '切換台語':'nan',
                         'switchtomandarin':'zh', 'switchtoenglish':'en', 'switchtotaigi':'nan'}
    if compact in language_commands:
        language = language_commands[compact]
        speech_service.select(language)
        return {'zh':'已切換華語服務。', 'en':'English service selected.',
                'nan':'已切換台語辨識佮發聲。'}[language]
    face_commands = {'登入我的臉': 'enroll', '登陸我的臉': 'enroll',
                     '註冊我的臉': 'enroll', '登錄我的臉': 'enroll', '辨識我是誰': 'recognize',
                     '你認得我嗎': 'recognize', '刪除我的臉': 'delete',
                     'enrollmyface': 'enroll', 'recognizeme': 'recognize',
                     'deletemyface': 'delete'}
    if compact in face_commands:
        from face_identity import run
        from body_bridge import status
        status('Face task starting…')
        result = run(face_commands[compact])
        status('Face task finished — see conversation for result')
        return result
    if any(phrase in compact for phrase in ('辨識物品', '辨識物件', '辨物', '你看見什麼',
                                             '你看到了什麼', '你看到什麼', '你看見了什麼',
                                             '看看前面', '幫我看一下', 'identifyobjects',
                                             'whatdoyousee')):
        from vision_query import describe
        return describe()
    if compact in ('開啟預覽', '開啟預覽視窗', '打開預覽', '開啟攝影機預覽', 'opencamerapreview'):
        from body_bridge import send
        sent = send({'type': 'camera_preview', 'mode': 'open'})
        return localized('已送出開啟右上方攝影機預覽的要求。', 'Camera preview opening requested.') if sent else localized('身體介面未連線，無法開啟預覽。', 'The interface is disconnected; camera preview cannot be opened.')
    if compact in ('關閉預覽', '關閉預覽視窗', '關閉攝影機預覽', 'closecamerapreview'):
        from body_bridge import send
        sent = send({'type': 'camera_preview', 'mode': 'close'})
        return localized('已送出隱藏預覽的要求，攝影機觀察服務仍保留。', 'Camera preview hidden; camera observation remains active.') if sent else localized('身體介面未連線，無法隱藏預覽。', 'The interface is disconnected; camera preview cannot be hidden.')

    if text_lower.strip() in ('stop', '停止', '停止播放', '停止音樂'):
        stopped = music.stop()
        return localized('已停止音樂。', 'Music stopped.') if stopped else localized('目前沒有可停止的音樂。', 'No music is currently playing.')

    # 1. Quick shutdown/exit command handling
    if "shutdown" in text_lower or "poweroff" in text_lower or "exit" in text_lower or "關機" in user_text:
        return localized('第二階段測試模式不執行關機，請從桌面手動操作。', 'Shutdown is disabled in this test mode. Please shut down manually.')

    from restaurants import is_request, search
    if is_request(user_text):
        from body_bridge import status
        status('Searching live restaurant listings…')
        result = search(user_text)
        dialogue('assistant', result['display'])
        status('Restaurant lookup finished — see conversation')
        return result['speech']

    # 2. 離線音樂點歌指令（支援「播放 XXX」、「點歌 XXX」、「放一首 XXX」、「隨機放音樂」）
    if any(k in user_text for k in ("放音樂", "播放音樂", "隨便放首歌")) or "play music" in text_lower:
        return search_and_play_offline_music("")

    music_match = re.match(r'^(?:重新播放|重播|再播放一次|播放|點歌|放一首|我想聽|play)\s*(.+)$', user_text, re.IGNORECASE)
    if music_match:
        keyword = music_match.group(1).strip()
        return search_and_play_offline_music(keyword)

    if user_text.strip() in ('取消點歌', '取消', 'cancel'):
        waiting_song_until = 0
        return localized('已取消點歌。', 'Song request canceled.')
    if time.monotonic() < waiting_song_until:
        return search_and_play_offline_music(user_text.strip())

    # 3. Forward transcribed voice text or keyboard prompt to Pi CLI
    print(f"🚀 Sending command to Pi CLI (cwd={AGENT_WORK_DIR}): {user_text}")

    prompt = speech_service.instruction(speech_service.selected()) + user_text

    started = time.monotonic()
    try:
        llm_metrics.begin()
    except OSError:
        pass
    try:
        result = subprocess.run(
            model_router.pi_command(prompt),
            cwd=AGENT_WORK_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            update_llm_failure('Request failed')
            return localized(
                'AI 模型請求失敗。請檢查目前模型供應商的登入或 API 憑證，以及服務連線；沒有自動切換模型。',
                'The AI request failed. Check the selected provider login/API credentials and service connection. No fallback model was used.')
        try:
            reply, metrics = llm_metrics.parse_result(result.stdout, time.monotonic() - started)
        except llm_metrics.ModelUnavailableError:
            update_llm_failure('Model unavailable')
            return localized(
                '我有收到你的話，但目前帳號無法使用所選模型。請到 AI Model 分頁選擇可用的線上模型，或切換到在地模型；尚未自動更換模型。',
                'I received your message, but the selected model is unavailable for this account. Choose an available model in AI Model or switch to Local. No model was changed automatically.')
        except RuntimeError:
            update_llm_failure('Request failed')
            return localized(
                '我有收到你的話，但 AI 服務未能完成回答。請檢查所選模型、帳號權限與連線；尚未自動切換模型。',
                'I received your message, but the AI service could not complete the reply. Check the selected model, account access and connection. No fallback model was used.')
        except ValueError:
            update_llm_failure('No response')
            return localized(
                '模型沒有傳回完整回答。請檢查目前模型的登入、連線與可用狀態；沒有自動切換模型。',
                'The model returned no complete reply. Check the selected model login, connection and availability. No fallback model was used.')
        try:
            llm_metrics.store(metrics)
        except OSError:
            pass

        if not reply and result.stderr:
            print(f"⚠️ Pi CLI stderr: {result.stderr}")
            return "執行指令時發生錯誤，請檢查終端機訊息。"

        return reply if reply else "指令已執行完成。"

    except FileNotFoundError:
        update_llm_failure('Unavailable')
        return "找不到 Pi 指令工具，請確認環境變數設定。"
    except subprocess.TimeoutExpired:
        update_llm_failure('Timeout')
        return "模型思考時間過長，請再試一次。"
    except Exception as e:
        update_llm_failure('Failed')
        return f"執行發生異常：{e}"

def update_llm_failure(status):
    try:llm_metrics.failed(status)
    except OSError:pass

# ================= 6. Main Loop =================
if __name__ == "__main__":
    # Start each voice session with capture enabled; runtime mute still works.
    microphone.set_muted(False)
    from camera_start import start_camera
    start_camera()
    print(f"📂 Agent working directory: {AGENT_WORK_DIR}")
    print(f"🎵 Offline music directory: {MUSIC_DIR}")
    startup_text = {'zh':'Neris-A 離線語音助理系統已準備就緒。',
                    'en':'Neris-A is ready.', 'nan':'你好，我是 Neris。'}
    offline_speak(startup_text[speech_service.selected()])

    vad_thread = threading.Thread(target=listen_vad_loop, daemon=True)
    vad_thread.start()

    from command_server import serve
    threading.Thread(target=serve, args=(command_queue,), daemon=True).start()

    input_thread = threading.Thread(target=keyboard_input_loop, daemon=True)
    input_thread.start()

    print("\n🎤 Listening and ⌨️ Keyboard prompt enabled.")

    try:
        while True:
            command = command_queue.get()
            if command == '__neris_vulcan_salute__':
                from vulcan_greeting import reply as greeting_reply
                greeting = greeting_reply(speech_service.selected())
                offline_speak(**greeting, body_action='vulcan_salute', speech_delay=1.2)
            elif command.startswith('__neris_music_feedback__:'):
                from music_feedback import phrase, PREFIX
                feedback = phrase(command[len(PREFIX):], speech_service.selected())
                if feedback:offline_speak(feedback)
            else:
                reply = process_pi_agent_command(command)
                if reply:
                    offline_speak(reply)
                else:
                    notify('idle')
            command_queue.task_done()

    except KeyboardInterrupt:
        notify('idle')
        print("\nVoice Agent terminated.")
        os._exit(0)  # 乾淨結束背景錄音執行緒，避免 PortAudio Segmentation fault
