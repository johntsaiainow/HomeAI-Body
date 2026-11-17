"""Local title matching with conservative typo and tone-free pinyin fallback."""
from pathlib import Path
import re
import sys
import unicodedata
sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))
try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None


def normalize(text):
    text = unicodedata.normalize('NFKC', text).lower()
    return ''.join(c for c in text if c.isalnum())


def title(path):
    text = Path(path).stem
    text = re.sub(r'^\d+[\s._-]*', '', text)
    return re.split(r'\s+-\s+', text)[-1].strip()


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        nxt = [i]
        for j, y in enumerate(b, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = nxt
    return row[-1]


def rank(keyword, paths):
    query = normalize(keyword)
    if not query:
        return []
    phonetic = lazy_pinyin(query) if lazy_pinyin else None
    candidates = {}
    for path in sorted(paths):
        name = normalize(title(path))
        if not name:
            continue
        score = 0
        if query == name:
            score = 1.0
        elif len(query) >= 2 and query in name:
            score = .9
        elif phonetic and phonetic == lazy_pinyin(name):
            score = .88
        else:
            limit = 2 if max(len(query),len(name)) >= 4 else 1
            delta = distance(query, name)
            similarity = 1 - delta / max(len(query),len(name))
            if len(query) >= 3 and delta <= limit and similarity >= .55:
                score = similarity * .8
            if phonetic and len(query) >= 3:
                other = lazy_pinyin(name)
                pd = distance(phonetic, other)
                ps = 1 - pd / max(len(phonetic),len(other))
                if pd <= limit and ps >= .55:
                    score = max(score, ps * .8)
        if score:
            previous = candidates.get(name)
            if previous is None or score > previous[0]:
                candidates[name] = (score, path, title(path))
    return sorted(candidates.values(), key=lambda item: (-item[0], item[2]))
