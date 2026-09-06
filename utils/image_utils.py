import requests
import logging

logger = logging.getLogger(__name__)

# NVIDIA NIM image endpoint. flux.1-dev is the one text-to-image model with a live
# hosted endpoint — schnell/qwen/sd3.5 are download-only and never respond.
# The API rejects cfg_scale <= 1, so 0 (the schnell convention) is not valid here.
NIM_IMAGE_MODEL = "black-forest-labs/flux.1-dev"
NIM_IMAGE_URL = f"https://ai.api.nvidia.com/v1/genai/{NIM_IMAGE_MODEL}"


def generate_images(prompts, api_key):
    """
    Generate images using NVIDIA NIM (FLUX.1-schnell)

    Args:
        prompts: List of image prompts
        api_key: NVIDIA NIM API key (nvapi-...)

    Returns:
        List of base64-encoded image data URLs
    """
    if not api_key:
        logger.error("NVIDIA API key not provided")
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    urls = []

    for i, prompt in enumerate(prompts):
        enhanced_prompt = _enhance_educational_prompt(prompt)
        logger.info(f"Generating image {i+1}/{len(prompts)} with FLUX.1-schnell...")

        payload = {
            "prompt": enhanced_prompt[:10000],
            "width": 1024,
            "height": 1024,
            "steps": 30,
            "cfg_scale": 7.0,
            "seed": 0,
            "samples": 1,
            "mode": "base",
        }

        try:
            response = requests.post(NIM_IMAGE_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()

            for artifact in response.json().get("artifacts", []):
                if artifact.get("finishReason") == "SUCCESS" and artifact.get("base64"):
                    urls.append(f"data:image/jpeg;base64,{artifact['base64']}")
                    logger.info(f"Successfully generated image {i+1}")
                else:
                    logger.warning(f"Image {i+1} not returned: {artifact.get('finishReason')}")
        except Exception as e:
            logger.error(f"Error generating image {i+1}: {e}")
            continue

    return urls


def _enhance_educational_prompt(original_prompt):
    """
    Enhance prompts for better educational visual content

    Args:
        original_prompt: Original image prompt

    Returns:
        Enhanced prompt with educational styling
    """
    # Asking for a "white background" alone drains all contrast out of flux.1-dev
    # (it renders white shapes on white). Naming the ink colour is what fixes it,
    # so this is appended unconditionally rather than only when style words are absent.
    style = (
        "flat vector infographic, bold dark navy and charcoal lines, "
        "black text labels, solid light grey background, strong contrast, "
        "sharp crisp edges, clean and professional"
    )
    return f"{original_prompt}, {style}"


def get_model_info():
    """
    Return information about the current models

    Returns:
        Dictionary with model information
    """
    return {
        "text_model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "image_model": NIM_IMAGE_MODEL,
        "provider": "NVIDIA NIM",
        "image_info": {
            "architecture": "Rectified Flow Transformer",
            "features": [
                "Guidance-distilled 12B model",
                "Strong prompt adherence",
                "Free prototyping tier"
            ],
            "native_resolution": "1024x1024",
            "recommended_steps": "30"
        }
    }
