"""Explicit LM Studio model swaps: unload old LLMs before loading a new one."""
import json
from pathlib import Path
import subprocess

CLI = Path.home() / '.lmstudio/bin/lms'


def run(args):
    try:
        result = subprocess.run([str(CLI), *args], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=150)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('LM Studio operation failed or timed out; model selection was not saved') from error
    if result.returncode:
        raise ValueError('LM Studio rejected the operation; the old model may already be unloaded')
    return result.stdout


def loaded():
    try:
        rows = json.loads(run(['ps', '--json']))
        if not isinstance(rows, list):raise ValueError()
        result = [row for row in rows if isinstance(row, dict) and row.get('type') == 'llm']
        if any(not isinstance(row.get('identifier'), str) or not row['identifier'] for row in result):
            raise ValueError()
        return result
    except (TypeError, json.JSONDecodeError):
        raise ValueError('Could not read loaded models safely') from None


def prepare(mode, provider, model):
    if mode != 'online' and provider != 'neris-a':
        raise ValueError('Automatic unload/load is only configured for the neris-a LM Studio provider')
    # Cloud selection also frees local LLM memory. Embeddings are never unloaded.
    rows = loaded()
    target = model if mode != 'online' else None
    if len(rows) == 1 and rows[0]['identifier'] == target:
        return
    if any(row.get('status', '').lower() not in ('idle', '') or row.get('queued', 0) for row in rows):
        raise ValueError('A local model is busy; wait for its request to finish before switching')
    for row in rows:
        if row['identifier'] != target:
            run(['unload', row['identifier']])
    remaining = loaded()
    if any(row['identifier'] != target for row in remaining):
        raise ValueError('Old model is still loaded; new model was not loaded')
    if target and not any(row['identifier'] == target for row in remaining):
        run(['load', model, '--identifier', model, '--yes'])
        if not any(row['identifier'] == target for row in loaded()):
            raise ValueError('New model loading was not confirmed; selection was not saved')
