import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import re
import time
import logging

logger = logging.getLogger(__name__)

def call_genai(api_key, topic, length, mode, previous_attempts=None):
    """
    Call Google Gemini AI to generate ML learning content
    
    Args:
        api_key: Gemini API key
        topic: ML topic to explain
        length: Length of explanation (Brief, Detailed, Comprehensive)
        mode: Output mode (Text explanation, Code with explanation, Audio, Image Explanation)
        previous_attempts: Previous attempts (for retry logic)
    
    Returns:
        Tuple of (briefing, code_content, audio_script, image_prompts)
    """
    genai.configure(api_key=api_key)
    
    # Enhanced prompt construction
    base_prompt = f"""
You are an expert educational tutor providing content for topics related to Computer Science, Software Development, Technology, Artificial Intelligence (AI), Machine Learning (ML), and Deep Learning (DL).

TOPIC SCOPE:
- You should respond to topics related to: AI, ML, Deep Learning, Computer Science, Software Engineering, Programming, Data Science, Algorithms, Computer Systems, and Technology.
- Examples of valid topics: KNN, neural networks, Python programming, data structures, algorithms, software design patterns, databases, web development, computer architecture, etc.
- Focus on educational and technical content.

Topic: "{topic}"
Required format: {mode}
Explanation depth: {length}

Teaching Guidelines:
- Start with a clear learning objective
- Provide structured explanations with examples
- Use appropriate technical depth for the topic
- Include practical applications when relevant
- Ensure accuracy and clarity
- Format output as clean text WITHOUT markdown symbols like #, *, **, etc.
- Use plain text formatting with clear paragraphs and line breaks
- For headings, use ALL CAPS or underlines instead of # symbols
- For emphasis, use uppercase or quotation marks instead of * or **
- NEVER include stage directions, meta-instructions, or non-content text like "[pause]", "(wait)", "pause here", etc.

"""
    
    code_instruction = ""
    audio_instruction = ""
    image_instruction = ""
    
    if mode == "Code with explanation":
        code_instruction = f"""
- You MUST also generate a Python program that demonstrates how {topic} works.
- Before the Python code block, provide a detailed but beginner-friendly explanation in markdown. This explanation should cover the model, key functions, and evaluation.
- The Python code itself should be enclosed in a single '```python' and '```' block.
- Include helpful comments in the code explaining key steps.
- Show expected outputs or results where applicable.
"""
    
    elif mode == "Audio":
        audio_instruction = """
- Also, provide a concise audio-ready script, clearly marked with 'Audio Script:' at the beginning of the script.
- CRITICAL: Write ONLY the actual spoken words - NO stage directions, NO meta-instructions, NO words like "pause", "[pause]", "(pause)", or any other non-spoken text.
- Write as if you are an experienced tutor naturally explaining the topic to a student in a conversation.
- Use natural conversational flow with complete sentences that sound good when spoken aloud.
- Use simple transitions between ideas (like "Now", "Next", "Let me explain", "For example", "This means that").
- Keep sentences clear, not too long, and easy to understand when listening.
- Use an engaging, enthusiastic teaching style that keeps the listener interested.
- Explain concepts step-by-step as if having a one-on-one tutoring session.
- DO NOT include ANY instructions, directions, or notes - only the actual words to be spoken.
"""
    
    elif mode == "Image Explanation":
        image_instruction = f"""
- Additionally, you MUST provide 2-3 text prompts for an image generation AI.
- CRITICAL FORMATTING RULES:
  * Each prompt MUST start on a brand new line with the exact marker 'IMG-PROMPT::' followed by the prompt text.
  * Create prompts for technical diagrams, educational visualizations, and concept illustrations related to {topic}.
  * Focus on clear, educational visual content: diagrams, flowcharts, architectural representations.
  * Use descriptive language for technical accuracy: "neural network architecture diagram", "decision tree visualization", "clustering algorithm illustration".
  * Include style guidance: "technical diagram style", "educational infographic", "clean minimalist design".
  * Specify backgrounds: "white background", "clean background", "professional presentation style".
  * All text in generated images MUST be in English.
"""
    
    # Combine all instructions
    prompt = base_prompt + code_instruction + audio_instruction + image_instruction
    
    # Add output format requirements
    prompt += """
Output Requirements:
- Provide clear, well-structured content
- DO NOT use any markdown formatting symbols (#, *, **, _, etc.)
- Use plain text with clear paragraph breaks for readability
- Do not add conversational elements like "I hope this helps"
- Focus on educational value and accuracy
- Format headings using ALL CAPS or line breaks, not # symbols
- Format emphasis using UPPERCASE or "quotation marks", not * or **
"""
    
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 60,
        "max_output_tokens": 4096
    }
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    
    max_retries = 3
    attempt = 0
    
    while attempt < max_retries:
        try:
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            response = model.generate_content(prompt)
            full_response_text = response.text
            
            # Initialize return values
            briefing, code_content, audio_script, image_prompts = full_response_text, "", "", []
            
            # Parse different modes
            if mode == "Code with explanation":
                code_match = re.search(r"```python\n(.*?)```", briefing, re.DOTALL)
                if code_match:
                    code_content = code_match.group(1).strip()
                    # Remove code block from briefing
                    briefing = briefing.replace(code_match.group(0), "").strip()
            
            elif mode == "Audio":
                if "Audio Script:" in briefing:
                    parts = briefing.split("Audio Script:", 1)
                    briefing, audio_script = parts[0].strip(), parts[1].strip()
            
            elif mode == "Image Explanation":
                marker = "IMG-PROMPT::"
                if marker in briefing:
                    first_marker_pos = briefing.find(marker)
                    briefing_text = briefing[:first_marker_pos].strip()
                    prompts_text = briefing[first_marker_pos:]
                    image_prompts = [p.strip() for p in prompts_text.split(marker) if p.strip()]
                    briefing = briefing_text
            
            return briefing, code_content, audio_script, image_prompts
            
        except google_exceptions.ResourceExhausted as e:
            logger.warning(f"Rate limit hit. Waiting 60 seconds before retrying... ({attempt + 1}/{max_retries})")
            time.sleep(60)
            attempt += 1
            continue
        except Exception as e:
            logger.error(f"An unexpected error occurred during the Gemini API call: {e}")
            return None
    
    logger.error("API call failed after multiple retries due to rate limiting.")
    return None
