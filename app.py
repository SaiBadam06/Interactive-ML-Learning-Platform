from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for
import os
import logging
from datetime import timedelta
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import requests
import secrets
import base64
import tempfile

# Import utility modules
from utils.genai_utils import call_genai, call_followup, explain_code_sections, generate_quiz
from utils.audio_utils import text_to_audio
from utils.code_executor import detect_dependencies, save_code_to_file
from utils.image_utils import generate_images, get_model_info
from utils import auth, quota

# Load environment variables
# Explicit path: bare load_dotenv() walks the call stack to locate the file,
# which can raise under an unusual import stack. On Vercel there is no .env at
# all (it is in .vercelignore); the platform supplies the environment.
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_ENV_FILE):
    load_dotenv(_ENV_FILE)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))

# The login cookie. HttpOnly (default) keeps it away from scripts, SameSite=Lax
# is what lets the JSON-only API bodies stand in for per-request CSRF tokens,
# and Secure is set wherever the app is actually served over HTTPS.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=bool(os.getenv('VERCEL')),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=auth.SESSION_HOURS),
)
if not auth.auth_enabled():
    logger.warning("Supabase is not configured: running without login. "
                   "Set SUPABASE_URL and SUPABASE_ANON_KEY to enable accounts.")

_SUBDIRS = ('uploads', 'generated_audio', 'generated_code')


def _resolve_data_dir():
    """
    Pick a directory the app can actually write to, and create the subfolders.

    Serverless filesystems are read-only apart from /tmp. Vercel imports this
    module directly as the function entrypoint, so this has to hold on its own
    rather than relying on a wrapper to set DATA_DIR first - getting that wrong
    crashed every request with
    "OSError: [Errno 30] Read-only file system: './uploads'".
    """
    candidates = [
        os.getenv('DATA_DIR'),
        # Set by Vercel and AWS Lambda respectively.
        '/tmp' if (os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME')) else None,
        '.',
        tempfile.gettempdir(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            for sub in _SUBDIRS:
                os.makedirs(os.path.join(candidate, sub), exist_ok=True)
            return candidate
        except OSError as e:
            logger.warning(f"Cannot use {candidate!r} for generated files: {e}")
    # Nothing was writable. Downloads will fail, but the app still serves pages.
    logger.error("No writable data directory found; file downloads will not work")
    return tempfile.gettempdir()


# Configuration
DATA_DIR = _resolve_data_dir()
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
AUDIO_DIR = os.path.join(DATA_DIR, 'generated_audio')
CODE_DIR = os.path.join(DATA_DIR, 'generated_code')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}
VALID_LENGTHS = {'Brief', 'Detailed', 'Comprehensive'}
VALID_LEVELS = {'Beginner', 'Intermediate', 'Advanced'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.environ['DATA_DIR'] = DATA_DIR  # utils/ read this to place their output


def read_request():
    """Validated (topic, length, level, api_key) from the JSON body, tolerant of bad input."""
    data = request.get_json(silent=True) or {}
    topic = str(data.get('topic') or '').strip()[:300]
    length = data.get('length') if data.get('length') in VALID_LENGTHS else 'Brief'
    level = data.get('level') if data.get('level') in VALID_LEVELS else 'Beginner'
    api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()
    return topic, length, level, api_key

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ===================== Login =====================
# Everything is private except the handful of endpoints below. A before_request
# gate rather than a decorator on each view: a new page cannot forget to opt in.
PUBLIC_ENDPOINTS = {'static', 'login', 'auth_callback', 'auth_session', 'logout'}


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
        return None
    return auth.guard()


@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    # Report-Only for now: Prism, Pyodide and the in-browser runner all need
    # eval and blob workers, so enforce only once the console is clean.
    response.headers.setdefault('Content-Security-Policy-Report-Only', (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' data: blob:; "
        "connect-src 'self' https://cdn.jsdelivr.net " + (auth.supabase_url() or '') + "; "
        "worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ))
    return response


def app_config(**extra):
    """The JSON block templates read their configuration from. Values reach the
    page as data, never as interpolated JavaScript."""
    data = {
        'supabase_url': auth.supabase_url(),
        'supabase_anon_key': auth.anon_key(),
        'csrf': auth.csrf_token(),
    }
    data.update(extra)
    return data


@app.context_processor
def inject_account():
    user = auth.current_user()
    return {
        'account': user,
        'account_is_admin': bool(user and auth.is_admin(user.get('email'))),
        'auth_on': auth.auth_enabled(),
    }


@app.route('/login')
def login():
    if auth.auth_misconfigured_on_vercel():
        return auth.not_configured_response()
    destination = auth.safe_next(request.args.get('next'))
    if auth.current_user():
        return redirect(destination)
    return render_template('login.html', app_config=app_config(next=destination))


@app.route('/auth/callback')
def auth_callback():
    """Where invite and password-reset links land. Public by necessity: the
    recipient has no account yet. The Supabase session arrives in the URL
    fragment, which never reaches the server."""
    if auth.auth_misconfigured_on_vercel():
        return auth.not_configured_response()
    return render_template('auth_callback.html', app_config=app_config(next='/'))


@app.route('/auth/session', methods=['POST'])
def auth_session():
    """Trade a Supabase access token for a Flask session cookie."""
    if not auth.csrf_ok():
        return jsonify({'error': 'Invalid request. Please reload the page.'}), 400
    allowed, retry_after = auth.rate_limit('auth', request.remote_addr or '-', 10, 600)
    if not allowed:
        return jsonify({'error': 'Too many attempts. Please wait and try again.'}), 429, {
            'Retry-After': str(retry_after)}
    data = request.get_json(silent=True) or {}
    user = auth.verify_token(str(data.get('access_token') or ''))
    if not user:
        return jsonify({'error': 'Could not sign you in.'}), 401
    auth.sign_in(user)
    return jsonify({'ok': True, 'next': auth.safe_next(data.get('next')),
                    'email': user['email'], 'admin': auth.is_admin(user['email'])})


@app.route('/logout', methods=['POST'])
def logout():
    if not auth.csrf_ok():
        return jsonify({'error': 'Invalid request. Please reload the page.'}), 400
    session.clear()
    return jsonify({'ok': True, 'next': '/login'})


def spend_quota(kind):
    """None when the generation may go ahead, otherwise the 429 to return."""
    user = auth.current_user()
    if not user:
        return None
    allowed, _, reset_at = quota.check_and_record(
        user['id'], kind, exempt=auth.is_admin(user.get('email')))
    if allowed:
        return None
    when = reset_at.astimezone().strftime('%H:%M') if reset_at else 'tomorrow'
    return jsonify({'error': 'Daily limit reached. Resets at %s.' % when, 'remaining': 0}), 429


# ===================== Admin: users and invites =====================

def _invite_email():
    """(email, error_response). One validation path for both invite actions."""
    if not auth.csrf_ok():
        return None, (jsonify({'error': 'Invalid request. Please reload the page.'}), 400)
    if not auth.invites_enabled():
        return None, (jsonify({'error': 'Invites are not configured.'}), 503)
    admin = auth.current_user()['email']
    allowed, retry_after = auth.rate_limit('invite', admin, 20, 3600)
    if not allowed:
        return None, (jsonify({'error': 'Too many invites this hour.'}), 429,
                      {'Retry-After': str(retry_after)})
    email = str((request.get_json(silent=True) or request.form or {}).get('email') or '').strip()
    if not auth.valid_email(email):
        return None, (jsonify({'error': 'That does not look like an email address.'}), 400)
    return email.lower(), None


@app.route('/admin/users')
@auth.admin_required
def admin_users():
    """List accounts. Rendered server-side so the secret key never leaves Flask."""
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    users, error = [], None
    if not auth.invites_enabled():
        error = 'not_configured'
    else:
        try:
            response = auth.admin_request('GET', '/admin/users',
                                          params={'page': page, 'per_page': 100})
            if response.status_code == 200:
                users = (response.json() or {}).get('users') or []
            else:
                error = 'unavailable'
        except (requests.RequestException, ValueError):
            error = 'unavailable'
    rows = [{
        'id': u.get('id'),
        'email': (u.get('email') or '').lower(),
        'created_at': (u.get('created_at') or '')[:10],
        'last_sign_in_at': (u.get('last_sign_in_at') or '')[:10],
        'pending': not u.get('last_sign_in_at'),
        'is_admin': auth.is_admin(u.get('email')),
    } for u in users if u.get('id')]
    return render_template('admin_users.html', users=rows, error=error, page=page,
                           has_next=len(rows) >= 100,
                           app_config=app_config())


def _generate_link(kind, email, redirect_to):
    """(action_link, status). Raises requests.RequestException on network trouble."""
    response = auth.admin_request('POST', '/admin/generate_link', json={
        'type': kind, 'email': email, 'redirect_to': redirect_to})
    if response.status_code >= 400:
        return None, response.status_code
    try:
        return (response.json() or {}).get('action_link') or None, response.status_code
    except ValueError:
        return None, response.status_code


@app.route('/admin/invite', methods=['POST'])
@auth.admin_required
def admin_invite():
    """Mint a one-use invite link, and optionally ask Supabase to email it.

    The link is the product. Supabase's built-in mailer is rate-limited and
    frequently silent, so the admin always gets a copyable URL back even when
    the email attempt fails - never a dead end.
    """
    email, failure = _invite_email()
    if failure:
        return failure
    body = request.get_json(silent=True) or {}
    admin = auth.current_user()['email']
    site = auth.safe_site_url(body.get('site'), request.host_url)
    redirect_to = site + '/auth/callback'

    try:
        link, status = _generate_link('invite', email, redirect_to)
        kind = 'invite'
        if not link and status in (400, 409, 422):
            # Already in auth.users (a pending invite whose link was lost, or a
            # real account). A recovery link lands on the same page and lets
            # them set a password, so the admin still has something to send.
            link, status = _generate_link('recovery', email, redirect_to)
            kind = 'recovery'
    except requests.RequestException:
        return jsonify({'error': 'Could not reach the account service. Nothing was sent.'}), 502
    if not link:
        logger.warning("Invite link for %s failed with %s", email, status)
        return jsonify({'error': 'Supabase would not create a link for that address. '
                                 'Check it is spelled correctly and try again.'}), 502

    email_sent, email_error = False, None
    if str(body.get('action') or '') == 'send':
        try:
            response = auth.admin_request('POST', '/invite', json={
                'email': email, 'data': {'invited_by': admin}})
            email_sent = response.status_code < 400
            if not email_sent:
                email_error = ('Supabase would not send the email (its built-in mailer is '
                               'rate-limited). Copy the link below and send it yourself.')
        except requests.RequestException:
            email_error = ('The email could not be sent. Copy the link below and send it '
                           'yourself.')
    logger.info("invite %s link created for %s by %s (email sent: %s)",
                kind, email, admin, email_sent)
    return jsonify({'ok': True, 'email': email, 'link': link, 'kind': kind,
                    'email_sent': email_sent, 'email_error': email_error,
                    'redirect_to': redirect_to})


@app.route('/admin/users/delete', methods=['POST'])
@auth.admin_required
def admin_delete_user():
    """Irreversible and cascading, so every refusal happens before the call out.

    Order matters: CSRF, then configuration, then the rate limit, then the shape
    of the input, then who the target actually is.
    """
    if not auth.csrf_ok():                                                    # 9
        return jsonify({'error': 'Invalid request. Please reload the page.'}), 400
    if not auth.invites_enabled():                                            # 13
        return jsonify({'error': 'Account management is not configured.'}), 503
    admin = auth.current_user()
    allowed, retry_after = auth.rate_limit('delete', admin['email'], 10, 3600)  # 14
    if not allowed:
        return jsonify({'error': 'Too many deletions this hour.'}), 429, {
            'Retry-After': str(retry_after)}

    body = request.get_json(silent=True) or request.form or {}
    user_id = str(body.get('user_id') or '').strip()
    if not user_id:                                                           # 5
        return jsonify({'error': 'Which account? No user was given.'}), 400
    if not auth.valid_uuid(user_id):                                          # 6
        return jsonify({'error': 'That is not a valid account id.'}), 400

    try:                                                                      # 7, 12
        found = auth.admin_request('GET', '/admin/users/' + user_id)
    except requests.RequestException:
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was deleted.'}), 502
    if found.status_code == 404:
        return jsonify({'error': 'That account no longer exists.'}), 404
    if found.status_code != 200:
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was deleted.'}), 502
    try:
        target = (found.json() or {}).get('email') or ''
    except ValueError:
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was deleted.'}), 502
    target = target.strip().lower()                                           # 17

    if str(body.get('confirm') or '').strip().lower() != target:              # 11
        return jsonify({'error': 'The typed email did not match.'}), 400
    if target == (admin.get('email') or '').strip().lower():                  # 3
        return jsonify({'error': 'You cannot delete your own account.'}), 400
    if auth.is_admin(target) and _remaining_admins(target) < 1:                # 4
        return jsonify({'error': 'This is the only admin account.'}), 400

    try:
        removed = auth.admin_request('DELETE', '/admin/users/' + user_id)
    except requests.RequestException:
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was deleted.'}), 502
    if removed.status_code == 404:                                            # 8
        return jsonify({'error': 'That account no longer exists.'}), 404
    if removed.status_code >= 300:                                            # 12
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was deleted.'}), 502
    auth.forget_user(user_id)
    logger.info("admin %s deleted user %s (%s)", admin['email'], target, user_id)
    return jsonify({'ok': True, 'email': target})


def _remaining_admins(target):
    """How many admin accounts would survive deleting ``target``. -1 when the
    count cannot be established, which is treated as "do not risk it"."""
    try:
        response = auth.admin_request('GET', '/admin/users', params={'page': 1, 'per_page': 100})
        if response.status_code != 200:
            return -1
        emails = {(u.get('email') or '').strip().lower() for u in (response.json() or {}).get('users') or []}
    except (requests.RequestException, ValueError):
        return -1
    return len({e for e in emails if auth.is_admin(e)} - {target})


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

@app.route('/practice')
def practice():
    """Practice page: quiz only, no explanation needed first"""
    return render_template('practice.html')

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
        topic, length, level, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        over_quota = spend_quota('text')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Text explanation", level=level)
        
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
        topic, length, level, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        over_quota = spend_quota('code')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Code with explanation", level=level)
        
        if result:
            briefing, code_content, _, _ = result
            if not code_content:
                return jsonify({'error': 'The model did not return a code block. Please try again.'}), 502
            
            # Detect dependencies
            dependencies = detect_dependencies(code_content) if code_content else []
            
            # Save code to file
            code_filename = save_code_to_file(code_content, topic) if code_content else None

            # The section-by-section breakdown is a second model call and used to
            # run here, which doubled this route to ~90 s before the learner saw
            # anything. The page now asks /api/code-sections for it separately.
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
        topic, length, level, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        over_quota = spend_quota('audio')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Audio", level=level)
        
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
        topic, length, level, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content with image prompts
        over_quota = spend_quota('images')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Image Explanation", level=level)
        
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
        level = data.get('level') if data.get('level') in VALID_LEVELS else 'Beginner'
        api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()

        if not question:
            return jsonify({'error': 'Question is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        over_quota = spend_quota('followup')
        if over_quota:
            return over_quota
        answer = call_followup(api_key, topic, context, history, question, level)
        if not answer:
            return jsonify({'error': 'No answer could be generated. Please try again.'}), 502
        return jsonify({'success': True, 'answer': answer})
    except Exception as e:
        logger.error(f"Error in follow_up: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/code-sections', methods=['POST'])
def code_sections():
    """Section-by-section breakdown of a program the page already has in hand."""
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get('code') or '')[:20000]
        topic = str(data.get('topic') or '').strip()[:300]
        api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()

        if not code.strip():
            return jsonify({'error': 'Code is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        over_quota = spend_quota('sections')
        if over_quota:
            return over_quota
        sections = explain_code_sections(api_key, code, topic)
        if not sections:
            return jsonify({'error': 'No section breakdown could be generated.'}), 502
        return jsonify({'success': True, 'sections': sections})
    except Exception as e:
        logger.error(f"Error in code_sections: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/quiz', methods=['POST'])
def quiz():
    """Multiple-choice self-check for a topic, optionally about material already shown."""
    try:
        topic, _, level, api_key = read_request()
        context = str((request.get_json(silent=True) or {}).get('context') or '')[:6000]

        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        over_quota = spend_quota('quiz')
        if over_quota:
            return over_quota
        result = generate_quiz(api_key, topic, context, level)
        if not result['questions']:
            return jsonify({'error': 'No quiz could be generated. Please try again.'}), 502
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"Error in quiz: {e}")
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
        port=int(os.getenv('PORT', 5000)),
        exclude_patterns=[
            os.path.join(os.path.abspath(CODE_DIR), '*'),
            os.path.join(os.path.abspath(AUDIO_DIR), '*'),
            os.path.join(os.path.abspath(UPLOAD_FOLDER), '*'),
        ],
    )
