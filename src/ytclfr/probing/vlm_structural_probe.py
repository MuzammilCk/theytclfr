import base64
from typing import Any
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
    """Send 4 frames to Gemini 3.1 Flash-Lite to probe structure."""
    if len(frames) != 4:
        logger.warning(f"Expected 4 frames, got {len(frames)}. Truncating or padding may fail.")
    
    settings = get_settings()
    
    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
    except ImportError:
        logger.error("google-genai SDK is not installed")
        return {"structural_video_type": "none", "overlay_text_density": 0.0}

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        
        prompt = "Classify the video structure into one of these exact categories: ['list', 'ranking', 'countdown', 'compilation', 'slideshow', 'infographic', 'none']. Also estimate overlay_text_density as a float from 0.0 to 1.0."
        
        contents = []
        for frame_bytes in frames:
            contents.append(
                types.Part.from_bytes(
                    data=frame_bytes,
                    mime_type="image/jpeg",
                )
            )
        contents.append(prompt)

        response = client.models.generate_content(
            model=settings.vlm_model,
            contents=contents,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": VLMResponse.model_json_schema(),
            },
        )
        
        result = VLMResponse.model_validate_json(response.text)
        
        valid_types = {'list', 'ranking', 'countdown', 'compilation', 'slideshow', 'infographic', 'none'}
        if result.structural_video_type not in valid_types:
            result.structural_video_type = "none"
            
        return result.model_dump()
        
    except APIError as e:
        logger.error(f"Gemini API error during VLM probe: {e}")
        return {"structural_video_type": "none", "overlay_text_density": 0.0}
    except Exception as e:
        logger.error(f"Unexpected error in VLM probe: {e}")
        return {"structural_video_type": "none", "overlay_text_density": 0.0}
