import os
from faster_whisper.vad import get_vad_model, get_speech_timestamps
import inspect

vad_model = get_vad_model()
print("VAD Model type:", type(vad_model))
print("Dir VAD model:", dir(vad_model))

sig = inspect.signature(get_speech_timestamps)
print("Signature get_speech_timestamps:", sig)
