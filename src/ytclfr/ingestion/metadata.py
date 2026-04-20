import subprocess
import json
from pathlib import Path
from dataclasses import dataclass

class MetadataError(Exception):
    pass

@dataclass
class VideoMetadata:
    duration_seconds: float
    width: int | None
    height: int | None
    video_codec: str | None
    audio_codec: str | None
    frame_rate: float | None
    file_size_bytes: int

def extract_metadata(video_path: Path) -> VideoMetadata:
    if not video_path.exists():
        raise MetadataError(f"File not found: {video_path}")
        
    cmd = [
        "ffprobe", 
        "-v", "quiet", 
        "-print_format", "json", 
        "-show_streams", 
        "-show_format", 
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as e:
        raise MetadataError("ffprobe not found") from e
    except subprocess.CalledProcessError as e:
        raise MetadataError(f"ffprobe failed: {e.stderr}") from e
        
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MetadataError("Could not parse ffprobe output") from e
        
    format_info = data.get("format", {})
    streams_info = data.get("streams", [])
    
    duration = format_info.get("duration")
    if duration is None:
        raise MetadataError("Duration not found in metadata")
        
    try:
        duration_seconds = float(duration)
    except ValueError:
        raise MetadataError("Invalid duration format")
        
    try:
        file_size_bytes = int(format_info.get("size", 0))
    except (ValueError, TypeError):
        file_size_bytes = 0
        
    width = None
    height = None
    video_codec = None
    audio_codec = None
    frame_rate = None
    
    for stream in streams_info:
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            video_codec = stream.get("codec_name")
            width = stream.get("width")
            height = stream.get("height")
            r_frame_rate = stream.get("r_frame_rate")
            if r_frame_rate and "/" in r_frame_rate:
                try:
                    num, den = r_frame_rate.split("/")
                    if den != "0":
                        frame_rate = float(num) / float(den)
                except ValueError:
                    pass
        elif codec_type == "audio":
            audio_codec = stream.get("codec_name")
            
    return VideoMetadata(
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        video_codec=video_codec,
        audio_codec=audio_codec,
        frame_rate=frame_rate,
        file_size_bytes=file_size_bytes,
    )
