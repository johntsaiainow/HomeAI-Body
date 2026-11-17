"""Local, line-synchronized LRC lyrics. No network or audio transcription."""
from bisect import bisect_right
from pathlib import Path
import re
from urllib.parse import unquote,urlparse

STAMP=re.compile(r'\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]')
OFFSET=re.compile(r'\[offset\s*:\s*([+-]?\d+)\]',re.I)
WORD=re.compile(r'<\d+:\d+(?:\.\d+)?>')


def parse_lrc(text):
    offsets=OFFSET.findall(text)
    offset=int(offsets[-1])/1000 if offsets else 0
    entries=[]
    for line in text.splitlines():
        tags=list(STAMP.finditer(line))
        if not tags:continue
        lyric=WORD.sub('',STAMP.sub('',line)).strip()
        for tag in tags:
            minute,second,fraction=tag.groups()
            time=int(minute)*60+int(second)+(int(fraction)/10**len(fraction) if fraction else 0)-offset
            entries.append((time,lyric))
    # Equal-time translations are displayed together, not silently discarded.
    groups={}
    for time,text in entries:groups.setdefault(time,[]).append(text)
    return [(time,'\n'.join(text for text in groups[time] if text)) for time in sorted(groups)]


def local_audio(value):
    if not isinstance(value,str) or not value:return None
    if value.startswith('file://'):
        url=urlparse(value)
        if url.netloc not in ('','localhost'):return None
        value=unquote(url.path)
    elif '://' in value:return None
    return Path(value).expanduser().absolute()


def sidecar(audio):
    direct=audio.with_suffix('.lrc')
    if direct.is_file():return direct
    try:
        for candidate in audio.parent.iterdir():
            if candidate.stem.casefold()==audio.stem.casefold() and candidate.suffix.lower()=='.lrc' and candidate.is_file():
                return candidate
    except OSError:pass
    return None


def read_lrc(path):
    with path.open('rb') as stream:raw=stream.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('LRC file exceeds 2 MB')
    encodings=('utf-16',) if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else ('utf-8-sig','big5','gb18030')
    for encoding in encodings:
        try:return parse_lrc(raw.decode(encoding))
        except UnicodeError:continue
    raise ValueError('Unsupported LRC encoding')


class Lyrics:
    def __init__(self):
        self.key=None;self.entries=[];self.times=[];self.error='';self.audio=None
    def update(self,filename,position):
        audio=local_audio(filename)
        path=sidecar(audio) if audio else None
        try:
            stat=path.stat() if path else None
            signature=(str(audio),str(path),stat.st_mtime_ns if stat else None,stat.st_size if stat else None)
        except OSError:signature=(str(audio),None,None,None);path=None
        if signature!=self.key:
            self.key=signature;self.audio=audio;self.entries=[];self.error=''
            if path:
                try:self.entries=read_lrc(path)
                except (OSError,ValueError) as error:self.error=str(error)
            self.times=[item[0] for item in self.entries]
        if not audio:return ('Lyrics · No music playing','','')
        if not self.entries:return ('Lyrics unavailable',self.error,'')
        if not isinstance(position,(int,float)):
            return ('Lyrics · Waiting for playback','',self.entries[0][1])
        index=bisect_right(self.times,position)-1
        current=self.entries[index][1] if index>=0 else ''
        following=self.entries[index+1][1] if index+1<len(self.entries) else ''
        return ('Lyrics',current,following)
