import requests
import re
import time
import logging

logger = logging.getLogger(__name__)

# NVIDIA NIM chat endpoint (OpenAI-compatible). Free tier, ~40 req/min.
NIM_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_TEXT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"

def call_genai(api_key, topic, length, mode, previous_attempts=None):
    """
    Call NVIDIA NIM to generate ML learning content
    
    Args:
        api_key: NVIDIA NIM API key (nvapi-...)
        topic: ML topic to explain
        length: Length of explanation (Brief, Detailed, Comprehensive)
        mode: Output mode (Text explanation, Code with explanation, Audio, Image Explanation)
        previous_attempts: Previous attempts (for retry logic)
    
    Returns:
        Tuple of (briefing, code_content, audio_script, image_prompts)
    """
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
- For headings, put the heading on its own line in Title Case, followed by a blank line. Never use # symbols.
- For emphasis, use "quotation marks" instead of * or **
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
- Your ENTIRE response is an audio script that will be read aloud verbatim. Do not write a separate written explanation, do not add headings, section titles or bullet points.
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
- Write in normal sentence case. Do NOT write sentences, paragraphs, code comments or headings in all capitals.
- Provide clear, well-structured content
- DO NOT use any markdown formatting symbols (#, *, **, _, etc.)
- Use plain text with clear paragraph breaks for readability
- Do not add conversational elements like "I hope this helps"
- Focus on educational value and accuracy
- Format headings as Title Case on their own line, not # symbols
- Format emphasis using "quotation marks", not * or **
"""

    # Mode markers go last: earlier in the prompt the formatting rules above
    # outrank them and the model drops the marker entirely.
    if mode == "Image Explanation":
        prompt += """
FINAL REQUIREMENT (do not skip):
After the written explanation, output 2-3 image prompts. Each one must start on its own line with the literal marker IMG-PROMPT:: written exactly like that. The marker is mandatory.
"""
    
    payload = {
        "model": NIM_TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 4096,
        # Nemotron is a reasoning model and otherwise streams its scratchpad into
        # `content`; learners only want the answer.
        "chat_template_kwargs": {"thinking": False},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        try:
            response = requests.post(NIM_CHAT_URL, headers=headers, json=payload, timeout=180)

            if response.status_code == 429:
                logger.warning(f"Rate limit hit. Waiting 60 seconds before retrying... ({attempt + 1}/{max_retries})")
                time.sleep(60)
                attempt += 1
                continue

            response.raise_for_status()
            full_response_text = response.json()["choices"][0]["message"]["content"]

            # Nemotron can emit a <think> reasoning block; it is not learner-facing content.
            full_response_text = re.sub(r"<think>.*?</think>", "", full_response_text, flags=re.DOTALL).strip()

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
                # Asking for explanation + marker + script was unreliable: the model
                # merged the parts and dropped the marker. The response is the script.
                audio_script = briefing

            elif mode == "Image Explanation":
                marker = "IMG-PROMPT::"
                if marker in briefing:
                    first_marker_pos = briefing.find(marker)
                    briefing_text = briefing[:first_marker_pos].strip()
                    prompts_text = briefing[first_marker_pos:]
                    image_prompts = [p.strip() for p in prompts_text.split(marker) if p.strip()]
                    briefing = briefing_text

            return briefing, code_content, audio_script, image_prompts

        except Exception as e:
            logger.error(f"An unexpected error occurred during the NVIDIA NIM API call: {e}")
            return None

    logger.error("API call failed after multiple retries due to rate limiting.")
    return None
