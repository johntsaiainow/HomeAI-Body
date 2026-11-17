"""Explicit eight-second microphone test; saves only when manually invoked."""
from pathlib import Path
import time
import wave
import sounddevice as sd

path = Path(__file__).resolve().parent / 'taigi_test.wav'
print('Recording starts in 3 seconds. Please speak a short Taigi sentence.', flush=True)
time.sleep(3)
print('Recording 8 seconds…', flush=True)
audio = sd.rec(8 * 16000, samplerate=16000, channels=1, dtype='int16')
sd.wait()
with wave.open(str(path), 'wb') as stream:
    stream.setnchannels(1)
    stream.setsampwidth(2)
    stream.setframerate(16000)
    stream.writeframes(audio.tobytes())
path.chmod(0o600)
print(f'Saved: {path}', flush=True)
