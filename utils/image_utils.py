import base64
import io
import logging
import time

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# NVIDIA NIM image endpoint. flux.1-dev is the only text-to-image model on
# build.nvidia.com with a live hosted endpoint - schnell, qwen-image and
# sd-3.5-large are download-only and either hang or 404.
NIM_IMAGE_MODEL = "black-forest-labs/flux.1-dev"
NIM_IMAGE_URL = f"https://ai.api.nvidia.com/v1/genai/{NIM_IMAGE_MODEL}"

# Measured on this endpoint: cfg 2.0 and 5.0 came back 1% ink (blank white),
# cfg 3.5 with the bold palette below came back 19%. The API rejects cfg <= 1
# and does not accept a negative_prompt at all.
CFG_SCALE = 3.5
STEPS = 30

# Naming the ink colours is what stops flux.1-dev rendering white-on-white.
# Never ask for a "white background" here - that alone drains the whole image.
STYLE = ("bold flat vector infographic, thick dark navy outlines, large solid colour blocks "
         "in navy teal and amber, high contrast, centered composition filling the whole frame, "
         # Without this the model draws "agent" as a human avatar rather than a box.
         "abstract labelled boxes and arrows only, schematic, no people, no human figures, no faces")

# Below this fraction of dark pixels the image is effectively blank.
MIN_INK_FRACTION = 0.04
MAX_ATTEMPTS = 3


def _ink_fraction(raw):
    """Fraction of pixels darker than mid-grey. Cheap blank-image detector."""
    try:
        img = Image.open(io.BytesIO(raw)).convert("L").resize((96, 96))
        px = list(img.getdata())
        return sum(1 for p in px if p < 128) / len(px)
    except Exception as e:
        logger.warning(f"Could not inspect image: {e}")
        return 1.0  # don't reject on inspection failure


def _enhance_educational_prompt(original_prompt, topic=None):
    """
    Build the final image prompt: the topic, the requested subject, then the
    house style. The style is always appended - the old code skipped it when the
    prompt already mentioned "diagram" or "background", which is exactly when
    flux.1-dev produced blank white images.
    """
    subject = " ".join(original_prompt.split())
    if topic and topic.lower() not in subject.lower():
        subject = f"{topic}: {subject}"
    return f"{subject}, {STYLE}"


def generate_images(prompts, api_key, topic=None):
    """
    Generate images using NVIDIA NIM (FLUX.1-dev).

    Args:
        prompts: List of image prompts
        api_key: NVIDIA NIM API key (nvapi-...)
        topic: Learner's topic, folded into each prompt to keep images on-subject

    Returns:
        List of base64-encoded image data URLs (JPEG)
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
        enhanced_prompt = _enhance_educational_prompt(prompt, topic)
        best = None  # keep the least-blank image seen, as a fallback

        for attempt in range(MAX_ATTEMPTS):
            logger.info(f"Generating image {i+1}/{len(prompts)} with FLUX.1-dev "
                        f"(attempt {attempt+1}/{MAX_ATTEMPTS})...")
            payload = {
                "prompt": enhanced_prompt[:10000],
                "width": 1024,
                "height": 1024,
                "steps": STEPS,
                "cfg_scale": CFG_SCALE,
                # A fresh seed per attempt: a blank result is usually this seed,
                # not this prompt, so retrying the same seed would just repeat it.
                "seed": attempt * 7919,
                "samples": 1,
                "mode": "base",
            }

            try:
                response = requests.post(NIM_IMAGE_URL, headers=headers, json=payload, timeout=120)
                # The free tier throws sporadic 500s; those are worth another try.
                if response.status_code >= 500 or response.status_code == 429:
                    raise requests.HTTPError(f"{response.status_code} from NIM")
                response.raise_for_status()

                artifact = next((a for a in response.json().get("artifacts", [])
                                 if a.get("finishReason") == "SUCCESS" and a.get("base64")), None)
                if not artifact:
                    logger.warning(f"Image {i+1} filtered or empty: {response.text[:120]}")
                    continue

                raw = base64.b64decode(artifact["base64"])
                ink = _ink_fraction(raw)
                if best is None or ink > best[0]:
                    best = (ink, artifact["base64"])

                if ink < MIN_INK_FRACTION:
                    logger.warning(f"Image {i+1} looks blank ({ink:.1%} ink); retrying with a new seed")
                    continue

                urls.append(f"data:image/jpeg;base64,{artifact['base64']}")
                logger.info(f"Successfully generated image {i+1} ({ink:.0%} ink)")
                break

            except Exception as e:
                logger.warning(f"Image {i+1} attempt {attempt+1}/{MAX_ATTEMPTS} failed: {e}")
                time.sleep(2 * (attempt + 1))
        else:
            # Every attempt was blank or failed: ship the best one rather than
            # dropping the image entirely, but say so.
            if best is not None:
                logger.warning(f"Image {i+1}: no attempt cleared the ink threshold; using best ({best[0]:.1%})")
                urls.append(f"data:image/jpeg;base64,{best[1]}")

    return urls


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
                "Blank-image detection with automatic reseed",
                "Free prototyping tier",
            ],
            "native_resolution": "1024x1024",
            "recommended_steps": str(STEPS),
        },
    }
