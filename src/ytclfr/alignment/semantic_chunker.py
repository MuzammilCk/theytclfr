def merge_segments_to_chunks(segments: list[dict], target_duration: float = 20.0, max_duration: float = 30.0) -> list[dict]:
    """Iterate through Whisper segments and merge them into semantic chunks."""
    chunks = []
    if not segments:
        return chunks
        
    current_chunk = None
    
    for seg in segments:
        if current_chunk is None:
            current_chunk = {
                "start_seconds": seg["start_seconds"],
                "end_seconds": seg["end_seconds"],
                "text": seg["text"].strip(),
                "source": seg.get("source", "asr")
            }
        else:
            current_chunk["text"] += " " + seg["text"].strip()
            current_chunk["end_seconds"] = seg["end_seconds"]
            
        duration = current_chunk["end_seconds"] - current_chunk["start_seconds"]
        text = current_chunk["text"]
        
        # Split condition: we hit target duration AND sentence ends, OR we hit max duration
        hit_target_and_boundary = duration >= target_duration and text.endswith(('.', '!', '?'))
        hit_max = duration >= max_duration
        
        if hit_target_and_boundary or hit_max:
            chunks.append(current_chunk)
            current_chunk = None
            
    if current_chunk is not None:
        chunks.append(current_chunk)
        
    return chunks
