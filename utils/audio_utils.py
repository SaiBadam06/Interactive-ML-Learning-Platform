from gtts import gTTS
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def clean_audio_script(text):
    """
    Clean the audio script by removing stage directions and non-spoken text.

    Args:
        text: Raw audio script text

    Returns:
        Cleaned text ready for text-to-speech
    """
    # Remove common stage directions and meta-instructions
    # Remove text in brackets [pause], [emphasis], etc.
    text = re.sub(r'\[.*?\]', '', text)

    # Remove text in parentheses (pause), (slow down), etc.
    text = re.sub(r'\(.*?\)', '', text)

    # Remove standalone direction words (case insensitive)
    direction_words = [
        r'\bpause\b', r'\bstop\b', r'\bwait\b', r'\bslow down\b',
        r'\bspeed up\b', r'\bemphasis\b', r'\brepeat\b',
        r'\btake a breath\b', r'\binhale\b', r'\bexhale\b'
    ]
    for pattern in direction_words:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove multiple spaces and clean up
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text

# gTTS produces roughly 750 bytes of MP3 per character of script. The API
# returns the audio inline as a data URI, and serverless hosts cap the response
# body a few MB, so a long "Comprehensive" script has to be trimmed.
MAX_TTS_CHARS = 3500


def _trim_to_sentence(text, limit):
    """Cut to at most `limit` characters, ending on a sentence boundary."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    trimmed = window[:cut + 1] if cut > limit // 2 else window
    logger.info(f"Audio script trimmed from {len(text)} to {len(trimmed)} chars for TTS")
    return trimmed.strip()


def text_to_audio(text, topic="ml_topic"):
    """
    Converts a string of text into an MP3 audio file using gTTS.
    Args:
        text: Text to convert to audio
        topic: Topic name for filename
    Returns:
        Filename of generated audio file or None if failed
    """
    if not text or not text.strip():
        logger.warning("Cannot generate audio from empty text.")
        return None

    try:
        # Clean the text to remove stage directions
        cleaned_text = clean_audio_script(text)
        cleaned_text = _trim_to_sentence(cleaned_text, MAX_TTS_CHARS)

        if not cleaned_text or not cleaned_text.strip():
            logger.warning("Text became empty after cleaning.")
            return None

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30]
        filename = f"{safe_topic}_{timestamp}.mp3"
        filepath = os.path.join(os.getenv('DATA_DIR', '.'), 'generated_audio', filename)

        # Generate audio with cleaned text
        # Using tld='com' for US English accent which sounds more natural
        # slow=False for normal speaking pace (not slow)
        tts = gTTS(text=cleaned_text, lang='en', slow=False, tld='com')
        tts.save(filepath)

        logger.info(f"Audio generated successfully: {filename}")
        return filename

    except Exception as e:
        logger.error(f"Failed to generate audio: {e}")
        return None
def delete_old_audio_files(max_age_hours=24):
    """
    Delete audio files older than specified hours
    
    Args:
        max_age_hours: Maximum age of files to keep in hours
    """
    try:
        audio_dir = os.path.join(os.getenv('DATA_DIR', '.'), 'generated_audio')
        if not os.path.exists(audio_dir):
            return
        
        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_hours * 3600
        
        for filename in os.listdir(audio_dir):
            filepath = os.path.join(audio_dir, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    logger.info(f"Deleted old audio file: {filename}")
    
    except Exception as e:
        logger.error(f"Error deleting old audio files: {e}")
