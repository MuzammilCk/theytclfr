class MetadataError(Exception):
    pass

def extract_metadata_pyav(video_path: str) -> dict:
    """Extract video metadata using PyAV."""
    try:
        import av
    except ImportError:
        raise MetadataError("PyAV is not installed.")

    try:
        import os
        container = av.open(video_path)
        
        video_stream = next((s for s in container.streams if s.type == 'video'), None)
        if not video_stream:
            raise MetadataError("No video stream found.")
            
        audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
        
        width = video_stream.width
        height = video_stream.height
        duration = float(container.duration) / av.time_base if container.duration else 0.0
        video_codec = video_stream.codec_context.name
        audio_codec = audio_stream.codec_context.name if audio_stream else None
        
        fps = float(video_stream.average_rate) if video_stream.average_rate else 0.0
        file_size_bytes = os.path.getsize(video_path)
        
        return {
            "width": width,
            "height": height,
            "duration": duration,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "fps": fps,
            "file_size_bytes": file_size_bytes
        }
    except Exception as e:
        raise MetadataError(f"Failed to read video metadata: {e}") from e
