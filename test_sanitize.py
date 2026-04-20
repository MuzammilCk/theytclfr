import yt_dlp
import json
ydl = yt_dlp.YoutubeDL({'quiet': True})

class MockPP:
    pass

info = {"test": 1, "merger": MockPP(), "list": [MockPP()]}
print("Before:", info)
sanitized = ydl.sanitize_info(info)
print("After sanitized:", sanitized)
try:
    print("JSON:", json.dumps(sanitized))
except TypeError as e:
    def safe_serialize(obj):
        try:
            return json.loads(json.dumps(obj))
        except TypeError:
            return json.loads(json.dumps(obj, default=lambda o: str(o)))
    print("Safe JSON:", json.dumps(safe_serialize(info)))
