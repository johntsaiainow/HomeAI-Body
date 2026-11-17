"""Opt-in LRCLIB lookup. Metadata only; strict matching and exclusive local writes."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import MUSIC_DIR
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from lyrics import parse_lrc,sidecar

SETTINGS=Path(__file__).with_name('lyrics-settings.json')
MUSIC_ROOT=MUSIC_DIR
API='https://lrclib.net/api'
MATCH_VERSION=5
try:
    from opencc import OpenCC
    _traditional=OpenCC('s2t').convert
    _simplified=OpenCC('t2s').convert
except ImportError:
    _traditional=lambda text:text
    _simplified=lambda text:text

def artist_aliases(name):
    try:
        groups=json.loads(Path(__file__).with_name('lyrics-artist-aliases.json').read_text())
        for group in groups:
            if normalize(name) in {normalize(item) for item in group}:
                return list(dict.fromkeys([name,group[0],_simplified(group[0])]))
    except (OSError,ValueError,TypeError):pass
    return [name]

def artist_key(name):
    aliases=artist_aliases(name)
    return normalize(aliases[1] if len(aliases)>1 else aliases[0])

def title_key(title,artist):
    # Strip explicit soundtrack credits only; never strip Live/Remix/Acoustic qualifiers.
    title=re.sub(r'\s*(?:[-–—]\s*|[（(]\s*)電影.*?(?:配樂|插曲|主題曲)[）)]?\s*$','',str(title))
    key=normalize(title)
    try:
        groups=json.loads(Path(__file__).with_name('lyrics-title-aliases.json').read_text())
        for group in groups:
            if artist_key(group['artist'])==artist_key(artist) and key in {normalize(t) for t in group['titles']}:
                return normalize(group['titles'][0])
    except (OSError,ValueError,TypeError,KeyError):pass
    return key

def select_candidate(records,query):
    matches={str(r.get('id')):r for r in records if matching(r,query)}
    rows=list(matches.values())
    if not rows:return None,[]
    album=normalize(query['album_name'])
    def album_score(row):
        candidate=normalize(row.get('albumName',''))
        if album and candidate==album:return 2
        if len(album)>=4 and candidate.startswith(album):return 1
        return 0
    score=max(map(album_score,rows))
    preferred=[r for r in rows if album_score(r)==score]
    if len(preferred)==1:return preferred[0],rows
    # Reissues sharing identical timestamped lyrics are equivalent for display.
    signatures={tuple((stamp,_traditional(text).strip()) for stamp,text in parse_lrc(r.get('syncedLyrics') or '')) for r in preferred}
    if len(signatures)==1 and next(iter(signatures)):
        return min(preferred,key=lambda r:abs(r['duration']-query['duration'])),rows
    return None,rows

def enabled():
    try:return json.loads(SETTINGS.read_text()).get('auto_download') is True
    except (OSError,ValueError,AttributeError):return False

def set_enabled(value):
    temporary=SETTINGS.with_suffix('.tmp')
    temporary.write_text(json.dumps({'auto_download':bool(value),'provider':'LRCLIB'},indent=2))
    temporary.replace(SETTINGS)

def normalize(value):
    return ''.join(c for c in _traditional(unicodedata.normalize('NFKC',str(value))).casefold() if c.isalnum())

def identity(audio,metadata,duration):
    tags={str(k).lower():v for k,v in metadata.items()} if isinstance(metadata,dict) else {}
    title=tags.get('title');artist=tags.get('artist') or tags.get('album_artist')
    if not title or not artist:
        parts=audio.stem.split(' - ',1)
        if len(parts)==2:
            artist=artist or parts[0];title=title or parts[1]
    if not isinstance(title,str) or not isinstance(artist,str) or not title.strip() or not artist.strip():return None
    if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:return None
    return {'track_name':title.strip(),'artist_name':artist.strip(),
            'album_name':str(tags.get('album') or '').strip(),'duration':float(duration)}

def matching(record,query):
    if not isinstance(record,dict):return False
    if title_key(record.get('trackName',''),query['artist_name'])!=title_key(query['track_name'],query['artist_name']):return False
    if artist_key(record.get('artistName',''))!=artist_key(query['artist_name']):return False
    duration=record.get('duration')
    return isinstance(duration,(float,int)) and math.isfinite(duration) and abs(duration-query['duration'])<=2

def api_get(endpoint,query):
    url=API+endpoint+'?'+urllib.parse.urlencode({k:v for k,v in query.items() if v!=''})
    req=urllib.request.Request(url,headers={'User-Agent':'Neris-A/2.0 (local desktop lyrics integration)','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=6) as response:
            raw=response.read(2_000_001)
    except urllib.error.HTTPError as error:
        if error.code==404:return None
        raise
    if len(raw)>2_000_000:raise ValueError('Provider response too large')
    return json.loads(raw)

def exclusive_write(path,text):
    # Never truncate a user-created file, including a concurrently created one.
    try:
        with path.open('x',encoding='utf-8') as stream:stream.write(text)
        return True
    except FileExistsError:return False

def fetch(audio,metadata,duration,allowed_root=MUSIC_ROOT,permission=enabled,lookup=api_get):
    audio=Path(audio)
    if not permission():return 'Auto Lyrics off'
    if not audio.resolve().is_relative_to(Path(allowed_root).resolve()):return 'Auto Lyrics · Outside music folder'
    if sidecar(audio):return 'Local lyrics available'
    query=identity(audio,metadata,duration)
    if query is None:return 'Auto Lyrics · Artist/title/duration required'
    report=audio.with_suffix('.lyrics-source.json')
    try:
        previous=json.loads(report.read_text())
        if previous.get('match_version')==MATCH_VERSION and previous.get('query')==query and time.time()<previous.get('retry_after',0):
            return previous.get('status','Lyrics unavailable')
    except (OSError,ValueError,TypeError,AttributeError):pass
    record=None;status='Lyrics unavailable · No confident match';ttl=86400;candidates=[]
    try:
        candidate=lookup('/get',query)
        if matching(candidate,query):record=candidate
        else:
            records=[]
            titles=list(dict.fromkeys([query['track_name'],_simplified(query['track_name']),_traditional(query['track_name'])]))
            for artist in artist_aliases(query['artist_name']):
                for title in titles:
                    if not permission():return 'Auto Lyrics off'
                    results=lookup('/search',{'track_name':title,'artist_name':artist})
                    if isinstance(results,list):records.extend(results)
            record,candidates=select_candidate(records,query)
            if record is None and not candidates:
                # Offer close-duration versions for explicit UI selection, never auto-adopt another singer.
                suggestions=[]
                for title in titles:
                    if not permission():return 'Auto Lyrics off'
                    results=lookup('/search',{'track_name':title})
                    if isinstance(results,list):
                        suggestions.extend(r for r in results if isinstance(r,dict)
                            and title_key(r.get('trackName',''),query['artist_name'])==title_key(query['track_name'],query['artist_name'])
                            and isinstance(r.get('duration'),(int,float))
                            and abs(r['duration']-query['duration'])<=2
                            and (r.get('syncedLyrics') or r.get('plainLyrics')))
                candidates=list({str(r.get('id')):r for r in suggestions}.values())
                if candidates:status='Lyrics · Choose a version below'
            elif record is None and candidates:status='Lyrics unavailable · Ambiguous versions'
        if record:
            synced=record.get('syncedLyrics');plain=record.get('plainLyrics')
            entries=parse_lrc(synced) if isinstance(synced,str) else []
            if record.get('instrumental') is True:status='Instrumental · No lyrics'
            elif entries and any(line.strip() for _,line in entries) and entries[-1][0]<=query['duration']+5:
                if permission() and not sidecar(audio):
                    saved=exclusive_write(audio.with_suffix('.lrc'),synced)
                    status='Synchronized lyrics downloaded' if saved else 'Local lyrics available'
            elif isinstance(plain,str) and plain.strip():
                if permission():
                    saved=exclusive_write(audio.with_suffix('.txt'),plain)
                    status='Plain lyrics saved · No timing' if saved else 'Plain lyrics exist · No timing'
            else:status='Lyrics unavailable · No usable lyrics'
    except (OSError,ValueError,TypeError) as error:
        status='Lyrics lookup failed';ttl=900
    if not permission():return 'Auto Lyrics off'
    provenance={'provider':'LRCLIB','api':API,'record_id':record.get('id') if record else None,
                'query':query,'status':status,'checked_at':time.time(),'retry_after':time.time()+ttl,
                'match_version':MATCH_VERSION,
                'matching':'Traditional/simplified, explicit artist-scoped title aliases, soundtrack-credit removal; artist aliases; duration <=2s; album preference, conflicting timing rejected',
                'selected_record':{k:record.get(k) for k in ('trackName','artistName','albumName','duration')} if record else None,
                'candidates':[{**{k:r.get(k) for k in ('id','trackName','artistName','albumName','duration')},
                               'has_synced':bool(r.get('syncedLyrics')),'has_plain':bool(r.get('plainLyrics'))} for r in candidates[:20]],
                'rights_note':'Third-party lyrics; provider availability is not a grant of copyright or commercial use rights.'}
    try:
        temporary=report.with_suffix('.json.tmp');temporary.write_text(json.dumps(provenance,ensure_ascii=False,indent=2));temporary.replace(report)
    except OSError:pass
    return status
