"""Persistent dialogue storage shared by stage-two voice and body."""
from datetime import datetime
import json
import os
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / 'logs/dialogue'


def save(role, text):
    now = datetime.now().astimezone()
    record = {'time': now.isoformat(), 'role': role, 'text': text}
    LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(LOG_DIR / f'{now:%Y-%m-%d}.jsonl'),
                 os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        update_outline(now.strftime('%Y-%m-%d'))
    except OSError as error:
        import sys
        print(f'每日大綱更新失敗（完整對話已保存）：{error}', file=sys.stderr)
    return record


def update_outline(day):
    """Rebuild an extractive daily digest; the JSONL remains authoritative."""
    from html import escape
    import tempfile
    source = LOG_DIR / f'{day}.jsonl'
    target_dir = LOG_DIR.parent / 'daily'
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = [f'# {day} 對話大綱', '',
             '> 自動文字節錄，非 AI 主題歸納；完整內容以對話日誌為準。', '',
             '| 時間 | 說話者 | 內容節錄 |', '| --- | --- | --- |']
    count = 0
    with source.open(encoding='utf-8') as stream:
        for line in stream:
            try:
                item = json.loads(line)
                if item.get('role') not in ('user', 'assistant') or not isinstance(item.get('text'), str):
                    continue
                text = ' '.join(item['text'].split())
                text = text[:180] + ('…' if len(text) > 180 else '')
                text = escape(text).replace('|', '&#124;').replace('`', '&#96;')
                stamp = str(item.get('time', ''))[11:19]
                role = '你' if item['role'] == 'user' else 'Neris-A'
                lines.append(f'| {stamp} | {role} | {text} |')
                count += 1
            except (ValueError, AttributeError):
                continue
    lines += ['', f'共 {count} 則訊息。', f'完整日誌：../dialogue/{day}.jsonl', '']
    filename = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target_dir,
                                         delete=False) as output:
            filename = output.name
            output.write('\n'.join(lines))
            output.flush()
            os.fsync(output.fileno())
        os.replace(filename, target_dir / f'{day}.md')
    finally:
        if filename and os.path.exists(filename):
            os.unlink(filename)


def recent(limit=200):
    from collections import deque
    records = deque(maxlen=limit)
    for path in sorted(LOG_DIR.glob('*.jsonl'), reverse=True):
        daily = deque(maxlen=limit)
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                    if (record.get('role') in ('user', 'assistant')
                            and isinstance(record.get('text'), str)):
                        daily.append(record)
                except (ValueError, AttributeError):
                    continue
        records = deque(list(daily) + list(records))
        if len(records) >= limit:
            return list(records)[-limit:]
    return list(records)
