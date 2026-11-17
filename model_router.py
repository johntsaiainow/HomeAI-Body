"""Neris-A Hybrid AI Model Router."""

import json
import os
import tempfile
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "config/model-router.json"
MODES = ("local", "qwen", "online")


def load():
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    if data.get("active") not in MODES:
        raise ValueError("Invalid active model profile")
    return data


def save(data):
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG.parent,
            delete=False,
        ) as f:
            name = f.name
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, CONFIG)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def current():
    data = load()
    mode = data["active"]
    profile = data["profiles"][mode]
    return mode, profile["provider"], profile["model"]


def switch(mode):
    if mode not in MODES:
        raise ValueError(f"Unknown model profile: {mode}")
    return _select(mode)


def select_model(mode, provider, model):
    """Save a model for one mode without changing the other mode's preference."""
    if mode not in ('local', 'online'):
        raise ValueError('Invalid model mode')
    if not all(isinstance(value, str) and value.strip() and not any(c.isspace() for c in value)
               for value in (provider, model)):
        raise ValueError('Invalid provider/model ID')
    return _select(mode, {'provider': provider, 'model': model})


def _select(mode, profile=None):
    import fcntl
    from model_lifecycle import prepare
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG.with_suffix('.switch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load()
        chosen = profile or data['profiles'][mode]
        if not chosen.get('provider') or not chosen.get('model'):
            raise ValueError('Model profile is not configured')
        prepare(mode, chosen['provider'], chosen['model'])
        data['profiles'][mode] = chosen
        data['active'] = mode
        save(data)
        return current()


def handle_command(text, english=False):
    """Handle explicit profile commands locally, never through the LLM."""
    import re
    command = re.sub(r'[\s，。！？,.!?]', '', text.lower())
    aliases = {
        '切換線上模型': 'online', '切換雲端模型': 'online',
        '使用線上模型': 'online', '使用雲端模型': 'online',
        'switchtoonline': 'online', 'switchtoonlinemodel': 'online',
        'switchtocloud': 'online', 'switchtocloudmodel': 'online',
        '切換在地模型': 'local', '使用在地模型': 'local',
        '切換本地模型': 'local', '切換本機模型': 'local',
        '使用本地模型': 'local', '使用本機模型': 'local',
        'switchtolocal': 'local', 'switchtolocalmodel': 'local',
    }
    queries = ('目前模型', '現在用什麼模型', 'currentmodel', 'whichmodel')
    if command not in aliases and command not in queries:
        return None
    try:
        mode, provider, model = switch(aliases[command]) if command in aliases else current()
        label = ('cloud' if mode == 'online' else 'local') if english else ('線上' if mode == 'online' else '本地')
        if command in queries:
            return f'Current model: {label}, {model}.' if english else f'目前使用{label}模型：{model}。'
        return (f'Selected {label} model: {model}. The next AI reply will use it; local model memory was managed; cloud access has not been tested.'
                if english else f'已切換{label}模型：{model}。下一次 AI 回答生效；在地模型已依先卸載再載入流程處理；線上服務權限未驗證。')
    except (OSError, ValueError, KeyError) as error:
        return f'Model selection failed ({type(error).__name__}).' if english else f'模型切換失敗（{type(error).__name__}）。'


def pi_command(prompt):
    _, provider, model = current()
    return [
        "pi",
        "--provider", provider,
        "--model", model,
        "--mode", "json",
        "--no-session",
        prompt,
    ]


if __name__ == "__main__":
    import sys

    try:
        if len(sys.argv) == 5 and sys.argv[1] == '--select':
            result = select_model(*sys.argv[2:])
        elif len(sys.argv) > 1:
            result = switch(sys.argv[1])
        else:
            result = current()
        print(json.dumps({'ok': True, 'selection': result}))
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        sys.exit(1)
