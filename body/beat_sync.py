"""Offline fixed-tempo estimate and cached video phase mapping (not beat-perfect tracking)."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import threading

ROOT = Path(__file__).resolve().parent


def phase(song_time, bpm, offset, duration, beats):
    rate = bpm * duration / (60 * beats)
    position = ((song_time - offset) * bpm / 60 % beats) * duration / beats
    return rate, position


def analyze(path):
    import numpy as np
    path = Path(path)
    stat = path.stat()
    key = hashlib.sha256(f'{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
    cache = ROOT.parent / 'cache/beats'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (key + '.json')
    if target.exists():
        return json.loads(target.read_text())
    # Limit analysis cost; a fixed tempo inferred from this segment may not fit the entire song.
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-t', '180',
                             '-vn', '-ac', '1', '-ar', '11025', '-f', 'f32le', 'pipe:1'],
                            capture_output=True, timeout=120, check=True)
    audio = np.frombuffer(result.stdout, dtype='<f4')
    hop, size, sr = 256, 512, 11025
    if len(audio) < sr * 5:
        raise ValueError('Not enough audio for tempo estimation')
    frames = np.lib.stride_tricks.sliding_window_view(audio, size)[::hop]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(size), axis=1))
    envelope = np.maximum(np.diff(np.log1p(spectrum), axis=0), 0).sum(axis=1)
    if float(envelope.max()) < 1e-6:
        raise ValueError('No usable onset signal')
    envelope = np.maximum(envelope - np.median(envelope), 0)
    n = len(envelope)
    fft_size = 1 << (2*n-1).bit_length()
    transform = np.fft.rfft(envelope, fft_size)
    correlation = np.fft.irfft(transform * transform.conj(), fft_size)[:n]
    minimum = math.ceil(60 * sr / (180 * hop))
    maximum = min(n-1, math.floor(60 * sr / (60 * hop)))
    candidates = np.arange(minimum, maximum + 1)
    scores = correlation[candidates] / np.maximum(1, n-candidates)
    # Broad 120-BPM prior resolves common half/double-tempo ambiguity;
    # this is a heuristic and can misread genuinely slow music.
    tempos = 60 * sr / (hop * candidates)
    scores *= np.exp(-0.5 * (np.log2(tempos / 120) / .6) ** 2)
    # Prefer the shortest strong local peak to reduce half-tempo aliases.
    peaks = [i for i in range(1, len(scores)-1)
             if scores[i] >= scores[i-1] and scores[i] >= scores[i+1]
             and scores[i] >= float(scores.max()) * .9]
    lag = int(candidates[peaks[0] if peaks else int(scores.argmax())])
    bpm = 60 * sr / (hop * lag)
    # Select a repeating onset phase; it is an estimate, not a downbeat annotation.
    bins = np.arange(n) % lag
    energies = np.bincount(bins, weights=envelope, minlength=lag)
    offset = (int(energies.argmax()) + 1) * hop / sr
    data = {'bpm': float(bpm), 'offset': float(offset), 'method': 'fixed_tempo_spectral_flux',
            'analyzed_seconds': min(180, len(audio)/sr), 'source': str(path)}
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(target)
    return data


class Analyzer:
    def __init__(self):
        self.path = None
        self.result = None
        self.error = None

    def select(self, path):
        if path == self.path:
            return
        self.path, self.result, self.error = path, None, None
        if not path:
            return
        def worker():
            try:
                result = analyze(path)
                if self.path == path:
                    self.result = result
            except Exception as error:
                if self.path == path:
                    self.error = str(error)
        threading.Thread(target=worker, daemon=True).start()
