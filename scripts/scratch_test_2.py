from faster_whisper.audio import decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps
import numpy as np

# Create dummy audio array (1 second of silence at 16000Hz)
audio = np.zeros(16000, dtype=np.float32)

try:
    vad_options = VadOptions(min_silence_duration_ms=500)
    segments = get_speech_timestamps(audio, vad_options=vad_options)
    print("VAD segments successfully generated:", segments)
except Exception as e:
    print("VAD error:", e)

try:
    from google import genai
    import os
    os.environ['OPENAI_BASE_URL'] = 'https://api.groq.com/openai/v1'
    client = genai.Client(api_key="fake")
    print("genai base_url with OPENAI_BASE_URL set:", client._api_client.base_url)
    
    client_fixed = genai.Client(api_key="fake", http_options={"base_url": "https://generativelanguage.googleapis.com"})
    print("genai fixed base_url:", client_fixed._api_client.base_url)
except Exception as e:
    print("genai error:", e)
