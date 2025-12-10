import requests
import base64
from google import genai
from google.genai import types
import logging
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

def generate_images(prompts, gemini_key, hf_key, backend):
    """
    Generate images using either Google Gemini or Hugging Face backend
    
    Args:
        prompts: List of image prompts
        gemini_key: Google Gemini API key
        hf_key: HuggingFace API key
        backend: Backend to use for generation
    
    Returns:
        List of base64-encoded image URLs
    """
    if backend == "Google Gemini (Fast & Free)":
        return _gen_with_gemini(prompts, gemini_key)
    else:
        return _gen_with_hf(prompts, hf_key)

def _gen_with_gemini(prompts, api_key):
    """Generate images using Gemini 2.0 Flash Preview Image Generation model"""
    try:
        # Configure the client
        client = genai.Client(api_key=api_key)
        urls = []
        
        for i, prompt in enumerate(prompts):
            try:
                # Enhance prompt for better educational content
                enhanced_prompt = _enhance_educational_prompt(prompt)
                
                logger.info(f"Generating image {i+1}/{len(prompts)} with Gemini...")
                
                # Use Gemini 2.0 Flash Preview Image Generation
                response = client.models.generate_content(
                    model="gemini-2.0-flash-preview-image-generation",
                    contents=f"Generate an image: {enhanced_prompt}",
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE']
                    )
                )
                
                # Extract image from response
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        img_bytes = part.inline_data.data
                        b64 = base64.b64encode(img_bytes).decode()
                        urls.append(f"data:image/png;base64,{b64}")
                        logger.info(f"Successfully generated image {i+1}")
                        break
                        
            except Exception as e:
                logger.error(f"Gemini API error for prompt {i+1}: {str(e)}")
                # Try with Imagen as fallback
                try:
                    logger.info("Trying Imagen fallback...")
                    response = client.models.generate_images(
                        model="imagen-3.0-generate-002",
                        prompt=enhanced_prompt,
                        config=types.GenerateImagesConfig(number_of_images=1)
                    )
                    
                    img_bytes = response.generated_images[0].image.image_bytes
                    b64 = base64.b64encode(img_bytes).decode()
                    urls.append(f"data:image/png;base64,{b64}")
                    logger.info(f"Successfully generated image {i+1} with Imagen")
                except Exception as e2:
                    logger.error(f"Imagen fallback failed: {str(e2)}")
                    continue
        
        return urls
    except Exception as e:
        logger.error(f"Gemini client initialization failed: {str(e)}")
        return []

def _gen_with_hf(prompts, api_key, model_id="stabilityai/stable-diffusion-xl-base-1.0"):
    """Generate images using Hugging Face Stable Diffusion with enhanced prompts"""
    if not api_key:
        logger.error("Hugging Face API key not provided")
        return []
    
    urls = []
    headers = {"Authorization": f"Bearer {api_key}"}
    
    for i, prompt in enumerate(prompts):
        try:
            # Enhance prompt for better educational content
            enhanced_prompt = _enhance_educational_prompt(prompt)
            
            logger.info(f"Generating image {i+1}/{len(prompts)} with HuggingFace SD...")
            
            # Enhanced payload for SDXL
            payload = {
                "inputs": enhanced_prompt,
                "parameters": {
                    "num_inference_steps": 28,
                    "guidance_scale": 7.0,
                    "width": 1024,
                    "height": 1024,
                    "scheduler": "DPMSolverMultistepScheduler"
                }
            }
            
            # Make the API request with retries for model loading
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"https://api-inference.huggingface.co/models/{model_id}",
                        headers=headers,
                        json=payload,
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        # Successful generation
                        content = response.content
                        b64 = base64.b64encode(content).decode()
                        urls.append(f"data:image/png;base64,{b64}")
                        logger.info(f"Successfully generated image {i+1}")
                        break
                    elif response.status_code == 503:
                        # Model loading - wait and retry
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 10
                            logger.info(f"Model loading... retrying in {wait_time}s")
                            import time
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.warning(f"Model unavailable after {max_retries} attempts")
                    elif response.status_code == 400:
                        # Bad request - try with simpler parameters
                        simple_payload = {"inputs": enhanced_prompt}
                        response = requests.post(
                            f"https://api-inference.huggingface.co/models/{model_id}",
                            headers=headers,
                            json=simple_payload,
                            timeout=120
                        )
                        
                        if response.status_code == 200:
                            content = response.content
                            b64 = base64.b64encode(content).decode()
                            urls.append(f"data:image/png;base64,{b64}")
                            logger.info(f"Successfully generated image {i+1}")
                            break
                        else:
                            logger.warning(f"HF API returned status {response.status_code}")
                    
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        logger.info(f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})")
                        continue
                    else:
                        logger.error("Request timed out after multiple attempts")
                except requests.exceptions.RequestException as e:
                    logger.error(f"HF API request failed: {str(e)}")
                    break
                    
        except Exception as e:
            logger.error(f"Error generating image {i+1}: {str(e)}")
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
    # Add educational visual style elements
    enhancements = [
        "educational diagram style",
        "clean and professional",
        "technical illustration",
        "white background",
        "high contrast",
        "clear and readable"
    ]
    
    # Check if prompt already has style guidance
    if not any(word in original_prompt.lower() for word in ["style", "background", "diagram", "illustration"]):
        enhanced = f"{original_prompt}, {', '.join(enhancements)}"
    else:
        enhanced = original_prompt
    
    return enhanced

def get_model_info():
    """
    Return information about the current models
    
    Returns:
        Dictionary with model information
    """
    return {
        "gemini_model": "gemini-2.0-flash-preview-image-generation",
        "gemini_fallback": "imagen-3.0-generate-002",
        "hf_model": "stabilityai/stable-diffusion-xl-base-1.0",
        "hf_info": {
            "parameters": "3.5B",
            "architecture": "Latent Diffusion Model",
            "features": [
                "High-resolution generation",
                "Better prompt adherence",
                "Enhanced image quality"
            ],
            "native_resolution": "1024x1024",
            "recommended_steps": "20-28"
        }
    }
