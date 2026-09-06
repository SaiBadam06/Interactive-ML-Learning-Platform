from flask import Flask, render_template, request, jsonify, session, send_file
import os
import logging
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import secrets
import base64

# Import utility modules
from utils.genai_utils import call_genai, call_followup
from utils.audio_utils import text_to_audio
from utils.code_executor import detect_dependencies, save_code_to_file
from utils.image_utils import generate_images, get_model_info

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))

# Configuration
# DATA_DIR: where generated files go. Serverless hosts (Vercel) only allow /tmp.
DATA_DIR = os.getenv('DATA_DIR', '.')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
AUDIO_DIR = os.path.join(DATA_DIR, 'generated_audio')
CODE_DIR = os.path.join(DATA_DIR, 'generated_code')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}
VALID_LENGTHS = {'Brief', 'Detailed', 'Comprehensive'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create necessary directories
for _d in (UPLOAD_FOLDER, AUDIO_DIR, CODE_DIR):
    os.makedirs(_d, exist_ok=True)


def read_request():
    """Validated (topic, length, api_key) from the JSON body, tolerant of bad input."""
    data = request.get_json(silent=True) or {}
    topic = str(data.get('topic') or '').strip()[:300]
    length = data.get('length') if data.get('length') in VALID_LENGTHS else 'Brief'
    api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()
    return topic, length, api_key

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/text-explanation')
def text_explanation():
    """Text explanation page"""
    return render_template('text_explanation.html')

@app.route('/code-generation')
def code_generation():
    """Code generation page"""
    return render_template('code_generation.html')

@app.route('/audio-learning')
def audio_learning():
    """Audio learning page"""
    return render_template('audio_learning.html')

@app.route('/image-visualization')
def image_visualization():
    """Image visualization page"""
    return render_template('image_visualization.html')

@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

# API Routes
@app.route('/api/generate-text', methods=['POST'])
def generate_text():
    """Generate text explanation"""
    try:
        topic, length, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        result = call_genai(api_key, topic, length, "Text explanation")
        
        if result:
            briefing, _, _, _ = result
            return jsonify({
                'success': True,
                'content': briefing
            })
        else:
            return jsonify({'error': 'Failed to generate content'}), 500
            
    except Exception as e:
        logger.error(f"Error in generate_text: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-code', methods=['POST'])
def generate_code():
    """Generate code with explanation"""
    try:
        topic, length, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        result = call_genai(api_key, topic, length, "Code with explanation")
        
        if result:
            briefing, code_content, _, _ = result
            if not code_content:
                return jsonify({'error': 'The model did not return a code block. Please try again.'}), 502
            
            # Detect dependencies
            dependencies = detect_dependencies(code_content) if code_content else []
            
            # Save code to file
            code_filename = save_code_to_file(code_content, topic) if code_content else None
            
            return jsonify({
                'success': True,
                'explanation': briefing,
                'code': code_content,
                'dependencies': dependencies,
                'filename': code_filename
            })
        else:
            return jsonify({'error': 'Failed to generate content'}), 500
            
    except Exception as e:
        logger.error(f"Error in generate_code: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-audio', methods=['POST'])
def generate_audio():
    """Generate audio explanation"""
    try:
        topic, length, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        result = call_genai(api_key, topic, length, "Audio")
        
        if result:
            briefing, _, audio_script, _ = result
            
            # Generate audio file
            audio_filename = text_to_audio(audio_script, topic) if audio_script else None
            if not audio_filename:
                return jsonify({'error': 'Audio could not be generated. Please try again.'}), 502
            
            with open(os.path.join(AUDIO_DIR, audio_filename), 'rb') as f:
                audio_data = 'data:audio/mpeg;base64,' + base64.b64encode(f.read()).decode()

            return jsonify({
                'success': True,
                'explanation': briefing,
                'script': audio_script,
                'audio_file': audio_filename,
                'audio_data': audio_data
            })
        else:
            return jsonify({'error': 'Failed to generate content'}), 500
            
    except Exception as e:
        logger.error(f"Error in generate_audio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-images', methods=['POST'])
def generate_images_api():
    """Generate images for visualization"""
    try:
        topic, length, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content with image prompts
        result = call_genai(api_key, topic, length, "Image Explanation")
        
        if result:
            briefing, _, _, image_prompts = result
            
            # Generate images
            image_urls = generate_images(image_prompts, api_key, topic) if image_prompts else []
            if not image_urls:
                return jsonify({'error': 'No images could be generated. NVIDIA image service may be busy - please try again.'}), 502
            
            return jsonify({
                'success': True,
                'explanation': briefing,
                'images': image_urls,
                'prompts': image_prompts
            })
        else:
            return jsonify({'error': 'Failed to generate content'}), 500
            
    except Exception as e:
        logger.error(f"Error in generate_images_api: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/follow-up', methods=['POST'])
def follow_up():
    """Answer a follow-up about content already shown. Stateless: the page sends its own history."""
    try:
        data = request.get_json(silent=True) or {}
        question = str(data.get('question') or '').strip()[:1000]
        topic = str(data.get('topic') or '').strip()[:300]
        context = str(data.get('context') or '')
        history = data.get('history') if isinstance(data.get('history'), list) else []
        api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()

        if not question:
            return jsonify({'error': 'Question is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        answer = call_followup(api_key, topic, context, history, question)
        if not answer:
            return jsonify({'error': 'No answer could be generated. Please try again.'}), 502
        return jsonify({'success': True, 'answer': answer})
    except Exception as e:
        logger.error(f"Error in follow_up: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/model-info', methods=['GET'])
def model_info():
    """Get model information"""
    try:
        info = get_model_info()
        return jsonify(info)
    except Exception as e:
        logger.error(f"Error in model_info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-code/<filename>')
def download_code(filename):
    """Download generated code file"""
    try:
        filepath = os.path.join(CODE_DIR, secure_filename(filename))
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Error in download_code: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-audio/<filename>')
def download_audio(filename):
    """Download generated audio file"""
    try:
        filepath = os.path.join(AUDIO_DIR, secure_filename(filename))
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Error in download_audio: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Generated .py and .mp3 files land inside the project tree, and the debug
    # reloader would otherwise restart the server mid-request when one is
    # written - the in-flight request dies and the client sees a 500.
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        exclude_patterns=[
            os.path.join(os.path.abspath(CODE_DIR), '*'),
            os.path.join(os.path.abspath(AUDIO_DIR), '*'),
            os.path.join(os.path.abspath(UPLOAD_FOLDER), '*'),
        ],
    )
