"""Persisted language and per-language ASR engine preference for stage two."""
import json
import os
from pathlib import Path
import tempfile

SETTINGS=Path(__file__).resolve().parent/'speech-service.json'
LANGUAGES=('zh','en','nan')
ENGINES=('auto','vosk','whisper')


def settings():
    try:
        value=json.loads(SETTINGS.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def save(value):
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=SETTINGS.parent,delete=False) as output:
            name=output.name;json.dump(value,output)
        os.replace(name,SETTINGS)
    finally:
        if name and Path(name).exists():Path(name).unlink()


def selected():
    language=settings().get('language','zh')
    return language if language in LANGUAGES else 'zh'


def backend(language=None):
    language=language or selected()
    choices=settings().get('asr_engines',{})
    engine=choices.get(language,'auto') if isinstance(choices,dict) else 'auto'
    return engine if engine in ENGINES else 'auto'


def ready(language,engine):
    if language=='nan' and engine=='vosk':return False
    if language=='en':
        names={'vosk':'vosk-model-small-en-us-0.15','whisper':'whisper-tiny.en'}
        engines=('vosk','whisper') if engine=='auto' else (engine,)
        return any((SETTINGS.parent.parent/'models'/names[e]/'DOWNLOAD_COMPLETE').is_file() for e in engines)
    return True


def select(language):
    if language not in LANGUAGES:raise ValueError('Unsupported speech language')
    if not ready(language,backend(language)):raise ValueError('Selected ASR engine/model is unavailable')
    value=settings();value['language']=language;save(value)


def set_backend(language,engine):
    if language not in LANGUAGES or engine not in ENGINES:raise ValueError('Unsupported ASR selection')
    if not ready(language,engine):raise ValueError('Selected ASR engine/model is unavailable')
    value=settings()
    if not isinstance(value.get('asr_engines'),dict):value['asr_engines']={}
    value['asr_engines'][language]=engine;save(value)


def instruction(language):
    return {'zh':'請用口語化的繁體中文簡短回答（50字以內，適合語音朗讀）：',
            'en':'Reply briefly in natural English, within 40 words, suitable for speech: ',
            'nan':'請用自然臺灣台語漢字簡短回答（50字以內，適合台語朗讀）；不要把華語句子冒充台語：'}[language]
