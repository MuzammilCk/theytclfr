import base64
from typing import Any
import httpx
from pydantic import BaseModel, Field

from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)

class VLMResponse(BaseModel):
    structural_video_type: str = Field(
        default="none",
        description="Must be one of: list, ranking, countdown, compilation, slideshow, infographic, none"
    )
    overlay_text_density: float = Field(default=0.0)

def probe_structure_vlm(frames: list[bytes]) -> dict[str, Any]:
    """Send 4 frames to Groq LLaMA Vision to probe structure."""
    if len(frames) != 4:
        logger.warning(f"Expected 4 frames, got {len(frames)}. Truncating or padding may fail.")
    
    settings = get_settings()
    api_key = settings.groq_api_key
    
    content = [
        {
            "type": "text",
            "text": "Classify the video structure into one of these exact categories: ['list', 'ranking', 'countdown', 'compilation', 'slideshow', 'infographic', 'none']. Also estimate overlay_text_density as a float from 0.0 to 1.0. Return a JSON object with keys 'structural_video_type' and 'overlay_text_density'. Do not return any other text."
        }
    ]
    
    for frame_bytes in frames:
        encoded = base64.b64encode(frame_bytes).decode('utf-8')
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encoded}"
            }
        })

    payload = {
        "model": "llama-3.2-11b-vision-preview",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        json_str = data["choices"][0]["message"]["content"]
        result = VLMResponse.model_validate_json(json_str)
        
        valid_types = {'list', 'ranking', 'countdown', 'compilation', 'slideshow', 'infographic', 'none'}
        if result.structural_video_type not in valid_types:
            result.structural_video_type = "none"
            
        return result.model_dump()
    except Exception as e:
        logger.error(f"VLM probe failed: {e}")
        return {"structural_video_type": "none", "overlay_text_density": 0.0}
