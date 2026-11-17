"""User-selected LRCLIB candidates. Cross-artist suggestions are never auto-applied."""
import json
from pathlib import Path
import time
from lyrics import parse_lrc,sidecar
from lyrics_download import MUSIC_ROOT,enabled,api_get,exclusive_write,title_key


def choices(audio):
    if not audio or sidecar(Path(audio)):return []
    try:
        report=json.loads(Path(audio).with_suffix('.lyrics-source.json').read_text())
        value=report.get('candidates',[])
        rows=[r for r in value if isinstance(r,dict) and isinstance(r.get('id'),int)][:20]
        duration=float(report.get('query',{}).get('duration',0))
        rows.sort(key=lambda r:(not r.get('has_synced'),abs(float(r.get('duration',0))-duration)))
        return rows
    except (OSError,ValueError,AttributeError):return []


def choose(audio,record_id,allowed_root=MUSIC_ROOT,permission=enabled,lookup=api_get):
    audio=Path(audio)
    if not permission():return 'Auto Lyrics off'
    if not audio.resolve().is_relative_to(Path(allowed_root).resolve()):return 'Outside music folder'
    if sidecar(audio):return 'Local lyrics preserved'
    report=audio.with_suffix('.lyrics-source.json')
    try:
        provenance=json.loads(report.read_text())
        if record_id not in [r['id'] for r in choices(audio)]:return 'Candidate expired; replay to refresh'
        query=provenance['query']
        record=lookup('/get/'+str(int(record_id)),{})
        if not isinstance(record,dict) or record.get('id')!=record_id:return 'Candidate unavailable'
        if title_key(record.get('trackName',''),query['artist_name'])!=title_key(query['track_name'],query['artist_name']):return 'Candidate title mismatch'
        if abs(float(record['duration'])-float(query['duration']))>2:return 'Candidate duration mismatch'
        if not permission():return 'Auto Lyrics off'
        synced=record.get('syncedLyrics');plain=record.get('plainLyrics')
        entries=parse_lrc(synced) if isinstance(synced,str) else []
        if entries and entries[-1][0]<=query['duration']+5 and any(line.strip() for _,line in entries):
            saved=exclusive_write(audio.with_suffix('.lrc'),synced)
            status='User-selected lyrics saved' if saved else 'Local lyrics preserved'
        elif isinstance(plain,str) and plain.strip():
            saved=exclusive_write(audio.with_suffix('.txt'),plain)
            status='Plain lyrics saved · No timing' if saved else 'Plain lyrics exist · No timing'
        else:return 'Candidate has no usable lyrics'
        provenance.update({'record_id':record_id,'status':status,'selection_method':'Explicit user choice in lyrics panel; not automatic artist equivalence',
            'selected_record':{k:record.get(k) for k in ('trackName','artistName','albumName','duration')},
            'auditory_sync_accepted':False,'selected_at':time.time(),'candidates':[]})
        temporary=report.with_suffix('.json.tmp');temporary.write_text(json.dumps(provenance,ensure_ascii=False,indent=2));temporary.replace(report)
        return status
    except (OSError,ValueError,KeyError,TypeError):return 'Candidate download failed'
