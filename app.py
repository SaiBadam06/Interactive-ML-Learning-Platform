from flask import (Flask, render_template, request, jsonify, session, send_file,
                   redirect, url_for, Response)
import json
import os
import logging
from datetime import timedelta
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import requests
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
import base64
import tempfile
from urllib.parse import quote

# Import utility modules
from utils.genai_utils import (call_genai, call_followup, explain_code_sections,
                               generate_quiz, stream_chat, AUDIENCE, WORDING, SCOPE,
                               _extract_code, NIM_TEXT_MODEL, NIM_CODE_MODEL)
from utils.audio_utils import text_to_audio
from utils.code_executor import (detect_dependencies, describe_packages,
                                 save_code_to_file)
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
    # On by default: set INSECURE_COOKIES=1 only for local http development.
    SESSION_COOKIE_SECURE=os.getenv('INSECURE_COOKIES', '') != '1',
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
# How hard the sentences are, asked separately from how deep the content goes.
VALID_WORDINGS = {'Simple', 'Standard'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.environ['DATA_DIR'] = DATA_DIR  # utils/ read this to place their output


def read_request():
    """Validated (topic, length, level, wording, api_key) from the JSON body.

    Tolerant of bad input: anything unrecognised falls back to the safe default
    rather than raising, because these arrive straight from a form.
    """
    data = request.get_json(silent=True) or {}
    topic = str(data.get('topic') or '').strip()[:300]
    length = data.get('length') if data.get('length') in VALID_LENGTHS else 'Brief'
    level = data.get('level') if data.get('level') in VALID_LEVELS else 'Beginner'
    wording = data.get('wording') if data.get('wording') in VALID_WORDINGS else 'Standard'
    api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()
    return topic, length, level, wording, api_key

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
    blocked = auth.guard()
    if blocked is not None:
        return blocked
    # The generation endpoints spend the deployment's API key and the signed-in
    # learner's quota, so they are state-changing. Enforced here rather than per
    # route for the same reason login is: a route added later cannot forget.
    # SameSite=Lax and the JSON content type already make a cross-site post hard;
    # this stops it depending on two side effects.
    if request.method == 'POST' and request.path.startswith('/api/') and not auth.csrf_ok():
        return jsonify({'error': 'Invalid request. Please reload the page.'}), 400
    return None


@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    # Nothing here uses a camera, a microphone or location, so refuse them
    # outright rather than leaving the decision to a future prompt.
    response.headers.setdefault(
        'Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
    # HSTS only where the connection is already TLS; sending it over plain http
    # would pin a scheme the local development server cannot serve.
    if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
        response.headers.setdefault('Strict-Transport-Security',
                                    'max-age=31536000; includeSubDomains')
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
        # The sign-out form in the nav is on every page, so the token has to be too.
        'csrf_token': auth.csrf_token(),
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
    # The nav signs out with an ordinary form, so answer one with a redirect
    # rather than a page full of JSON. Callers that asked for JSON still get it.
    if request.headers.get('X-CSRF-Token'):
        return jsonify({'ok': True, 'next': '/login?signed_out=1'})
    # signed_out tells the login page to end the Supabase session too. Without
    # it, clearing the Flask cookie achieves nothing: the browser still holds a
    # valid Supabase session and the page silently trades it for a new cookie,
    # so "Sign out" put you straight back in.
    return redirect(url_for('login', signed_out=1))


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
    default_limit = quota.daily_limit()
    rows = []
    for u in users:
        if not u.get('id'):
            continue
        # The override rides along in the listing, so showing it costs no extra
        # request per account.
        override = ((u.get('app_metadata') or {}).get(quota.META_KEY))
        try:
            override = int(override) if override is not None else None
        except (TypeError, ValueError):
            override = None
        rows.append({
            'id': u.get('id'),
            'email': (u.get('email') or '').lower(),
            'created_at': (u.get('created_at') or '')[:10],
            'last_sign_in_at': (u.get('last_sign_in_at') or '')[:10],
            'pending': not u.get('last_sign_in_at'),
            'is_admin': auth.is_admin(u.get('email')),
            'limit': override if override is not None else default_limit,
            'custom_limit': override is not None,
            'used': quota.used_today(u.get('id')) or 0,
        })
    return render_template('admin_users.html', users=rows, error=error, page=page,
                           has_next=len(rows) >= 100,
                           default_limit=default_limit,
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


@app.route('/admin/users/limit', methods=['POST'])
@auth.admin_required
def admin_set_limit():
    """Give one account its own daily allowance, or put it back on the default.

    Same order of refusals as the delete path: CSRF, configuration, the shape of
    the input, then the account itself.
    """
    if not auth.csrf_ok():
        return jsonify({'error': 'Invalid request. Please reload the page.'}), 400
    if not auth.invites_enabled():
        return jsonify({'error': 'Account management is not configured.'}), 503

    body = request.get_json(silent=True) or {}
    user_id = str(body.get('user_id') or '').strip()
    if not auth.valid_uuid(user_id):
        return jsonify({'error': 'That is not a valid account id.'}), 400

    raw = body.get('limit')
    if raw in (None, '', 'default'):
        limit = None                              # back to the deployment default
    else:
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            return jsonify({'error': 'The limit has to be a whole number.'}), 400
        if limit < 0:
            return jsonify({'error': 'The limit cannot be negative.'}), 400
        if limit > 10000:
            return jsonify({'error': 'That is higher than the API could serve. '
                                     'Use 0 for unlimited instead.'}), 400

    if not quota.set_limit(user_id, limit):
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was changed.'}), 502
    logger.info("admin %s set the daily limit for %s to %s",
                auth.current_user()['email'], user_id, limit if limit is not None else 'default')
    return jsonify({'ok': True, 'limit': limit, 'effective': quota.limit_for(user_id)})


@app.route('/admin/users/reset-usage', methods=['POST'])
@auth.admin_required
def admin_reset_usage():
    """Clear an account's usage for the current window, so it starts again."""
    if not auth.csrf_ok():
        return jsonify({'error': 'Invalid request. Please reload the page.'}), 400
    if not auth.invites_enabled():
        return jsonify({'error': 'Account management is not configured.'}), 503

    body = request.get_json(silent=True) or {}
    user_id = str(body.get('user_id') or '').strip()
    if not auth.valid_uuid(user_id):
        return jsonify({'error': 'That is not a valid account id.'}), 400

    if not quota.reset_usage(user_id):
        return jsonify({'error': 'Could not reach the account service. '
                                 'Nothing was changed.'}), 502
    logger.info("admin %s reset today's usage for %s", auth.current_user()['email'], user_id)
    return jsonify({'ok': True, 'used': quota.used_today(user_id) or 0})



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
    """The chat is the way in now. The old home page was a topic box and four
    buttons choosing which page to land on; the composer asks the same question
    and answers it in place."""
    return redirect(url_for('chat_page'))

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
    """Settings page. Usage is only meaningful when there is an account to
    count against, so it is fetched only then and never blocks the page."""
    user = auth.current_user()
    used = limit = None
    if user and auth.auth_enabled():
        try:
            used, limit = quota.used_today(user['id']), quota.daily_limit()
        except Exception:                      # usage is informational, not load-bearing
            logger.warning("Could not read today's usage", exc_info=True)
    return render_template('settings.html', usage_today=used, usage_limit=limit)

@app.route('/about')
def about():
    """About was folded into Settings; the old URL keeps working."""
    return redirect(url_for('settings') + '#about')


@app.route('/api/generate-text', methods=['POST'])
def generate_text():
    """Generate text explanation"""
    try:
        topic, length, level, wording, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        over_quota = spend_quota('text')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Text explanation", level=level, wording=wording)
        
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
        topic, length, level, wording, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        over_quota = spend_quota('code')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Code with explanation", level=level, wording=wording)
        
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
        topic, length, level, wording, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content
        over_quota = spend_quota('audio')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Audio", level=level, wording=wording)
        
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
        topic, length, level, wording, api_key = read_request()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
        
        # Generate content with image prompts
        over_quota = spend_quota('images')
        if over_quota:
            return over_quota
        result = call_genai(api_key, topic, length, "Image Explanation", level=level, wording=wording)
        
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
        wording = data.get('wording') if data.get('wording') in VALID_WORDINGS else 'Standard'
        api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()

        if not question:
            return jsonify({'error': 'Question is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        over_quota = spend_quota('followup')
        if over_quota:
            return over_quota
        answer = call_followup(api_key, topic, context, history, question, level, wording)
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
        wording = data.get('wording') if data.get('wording') in VALID_WORDINGS else 'Standard'
        api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()

        if not code.strip():
            return jsonify({'error': 'Code is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        over_quota = spend_quota('sections')
        if over_quota:
            return over_quota
        sections = explain_code_sections(api_key, code, topic, wording)
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
        topic, _, level, wording, api_key = read_request()
        context = str((request.get_json(silent=True) or {}).get('context') or '')[:6000]

        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        over_quota = spend_quota('quiz')
        if over_quota:
            return over_quota
        result = generate_quiz(api_key, topic, context, level, wording)
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


# ===================== Chat =====================
# One conversational surface. Everything the separate pages do is reachable by
# asking, and a follow-up is the next message rather than a different box
# further down the page.
#
# Every mode streams its text first, so words appear in about a second instead
# of after a 15-90 s spinner. Audio and images then produce their artifact from
# that same text and send it as a final event - the learner is already reading
# while the file is being made.

VALID_MODES = {'explain', 'code', 'audio', 'images', 'walkthrough'}

# What the page shows while each mode runs, so an inferred choice is visible
# rather than something that silently happened to the learner.
MODE_LABEL = {
    'explain': 'Explaining it',
    'code': 'Writing the program',
    'audio': 'Reading it aloud',
    'images': 'Drawing it',
    'walkthrough': 'Reading your code',
}

# ---------------------------------------------------------------- mode routing
# The composer used to make the learner pick the mode before asking. They know
# what they want in the words they already typed, so those are read instead and
# the picker is only there to override it.
#
# Deliberately keywords and not a model call: routing has to happen before the
# first token, and a second round trip to decide what to do would add its own
# latency to every single message.

# A fence, with whatever the model or the learner labelled it.
_FENCE = re.compile(r'```[\w+.\-]*\r?\n(.*?)(?:```|\Z)', re.DOTALL)

# Lines that are Python rather than a sentence about Python. An `=` alone is not
# enough - "accuracy = 0.9" is a thing people write in prose.
_CODE_LINE = re.compile(
    r'^\s*(?:import\s+\w|from\s+[\w.]+\s+import\s|def\s+\w+\s*\(|'
    r'class\s+\w+\s*[:(]|return\s|for\s+\w+\s+in\s+.+:|while\s+.+:|'
    r'if\s+.+:|elif\s+.+:|else\s*:|try\s*:|except\b|with\s+.+:|@\w+|'
    r'print\s*\(|\w+\s*=\s*\w+\s*[.(\[])',
    re.MULTILINE)

_WANT_AUDIO = re.compile(
    r'\b(listen|aloud|out loud|audio|narrat\w*|podcast|say it|read it to me|'
    r'hear (?:it|this)|spoken|voice)\b', re.I)
_WANT_IMAGES = re.compile(
    r'\b(diagram|picture|image|draw|drawing|sketch|visual\w*|illustrat\w*|'
    r'flowchart|chart of|show me what)\b', re.I)
_WANT_CODE = re.compile(
    r'\b(code|program|script|implement\w*|snippet|in python|notebook|'
    r'write (?:me )?(?:a|the)\b)', re.I)


def extract_pasted_code(text):
    """The code in a message, or ''.

    A fence wins outright. Without one, the message itself counts as code only
    when several lines are unmistakably Python - otherwise "if the loss is high
    then the model is underfitting" would be read as a program.
    """
    text = str(text or '')
    fenced = [block.strip() for block in _FENCE.findall(text)]
    fenced = [block for block in fenced if block]
    if fenced:
        return max(fenced, key=len)

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 3 and len(_CODE_LINE.findall(text)) >= 2:
        return text.strip()
    return ''


def route_mode(text):
    """Which mode the learner's own words ask for. Never raises."""
    text = str(text or '')

    # Code in the message is the strongest signal there is - unless they said
    # plainly that they want to hear it or see it drawn instead.
    if extract_pasted_code(text):
        if _WANT_AUDIO.search(text):
            return 'audio'
        if _WANT_IMAGES.search(text):
            return 'images'
        return 'walkthrough'

    # Most specific first: "read it aloud" and "draw me a diagram" mean one
    # thing each, where "code" turns up in questions that are not asking for any.
    if _WANT_AUDIO.search(text):
        return 'audio'
    if _WANT_IMAGES.search(text):
        return 'images'
    if _WANT_CODE.search(text):
        return 'code'
    return 'explain'

# How long a reply may spend reasoning before producing a word.
THINKING_BUDGET = 75          # seconds
IMAGE_BUDGET = 120            # seconds for the three diagrams

CHAT_SYSTEM = (
    "You are a patient tutor for artificial intelligence and machine learning.\n"
    "{scope}"
    "{audience}{wording}"
    "Rules for every reply:\n"
    # The page-based flows forbid markdown because they render plain text. The
    # chat renders it, and without it an answer that names half a dozen
    # functions arrives as one undifferentiated wall.
    "- Use markdown, and use it to make the answer easier to scan:\n"
    "  `backticks` around every identifier, function, argument and file name;\n"
    "  **bold** for a term you are defining, once, where you define it;\n"
    "  bullets starting with - when you list more than two things;\n"
    "  ### short headings only when the answer has genuinely separate parts.\n"
    "- Put runnable code in a ```python fence, never inline.\n"
    "- Keep paragraphs to three or four sentences with a blank line between "
    "them. A wall of text is the thing to avoid.\n"
    "- Answer the question actually asked. Do not restate the whole topic when "
    "the learner asks about one part of it.\n"
    "- If you are asked to simplify, say the same thing in easier words. Do not "
    "add new material and do not skip any of it.\n"
)

MODE_SYSTEM = {
    'code': (
        "\nThe learner asked for a program. Write one complete, runnable Python "
        "program in a single ```python fence. It must run end to end with no edits "
        "and print its results. Comment the parts that carry the idea. After the "
        "fence, explain in a few sentences what the program does.\n"
    ),
    'audio': (
        "\nThe learner wants to listen to this rather than read it. Write it as "
        "something spoken aloud: full sentences, no lists, no code, and no symbols "
        "a voice cannot say. Never write stage directions such as [pause]. Aim for "
        "about 250 words.\n"
    ),
    'walkthrough': (
        "\nThe learner has pasted code and wants to understand it. Explain their "
        "code - do not rewrite it, do not paste it back, and do not suggest "
        "improvements unless they asked for them. Cover, in this order: what the "
        "program does as a whole, in two or three sentences; what it needs to run "
        "and what it prints or produces; and the one idea somebody has to grasp "
        "before the rest of it makes sense. A section-by-section breakdown and the "
        "list of packages are added underneath automatically, so do not produce "
        "either yourself.\n"
    ),
    'images': (
        "\nThe learner wants a picture of this. First explain the idea in a few "
        "sentences. Then, on their own lines at the very end, write exactly three "
        "descriptions of diagrams that would make it clearer, each line starting "
        "with 'DIAGRAM: ' and describing only boxes, arrows and labels.\n"
    ),
}

# Which quota bucket each mode spends.
MODE_QUOTA = {'explain': 'text', 'code': 'code', 'audio': 'audio', 'images': 'images',
              'walkthrough': 'sections'}


def _sse(event):
    """One server-sent event."""
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@app.route('/chat')
def chat_page():
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Stream a reply as server-sent events.

    Auth, quota and every value the generator needs are resolved here, while the
    request context still exists. The generator body runs after Flask has torn
    that context down, so reading `request` or `session` inside it would fail.
    """
    data = request.get_json(silent=True) or {}
    api_key = str(data.get('api_key') or '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()
    if not api_key:
        return jsonify({'error': 'API key is required'}), 400

    # 'auto' - the default - means read it off the question. Anything else is
    # the learner overriding that from the picker.
    wanted = data.get('mode')
    mode = wanted if wanted in VALID_MODES else 'auto'
    level = data.get('level') if data.get('level') in VALID_LEVELS else 'Beginner'
    wording = data.get('wording') if data.get('wording') in VALID_WORDINGS else 'Standard'

    history = data.get('messages') if isinstance(data.get('messages'), list) else []
    turns = [{'role': m['role'], 'content': str(m['content'])[:6000]}
             for m in history[-12:]
             if isinstance(m, dict) and m.get('role') in ('user', 'assistant')
             and str(m.get('content') or '').strip()]
    if not turns or turns[-1]['role'] != 'user':
        return jsonify({'error': 'The last message must be yours.'}), 400
    question = turns[-1]['content']
    topic = question[:120]

    if mode == 'auto':
        mode = route_mode(question)
    # Only the walkthrough needs the code itself; extracting it for every mode
    # would run the pattern over messages that have none.
    pasted = extract_pasted_code(question) if mode == 'walkthrough' else ''
    if mode == 'walkthrough' and not pasted:
        mode = 'explain'                        # nothing to walk through after all

    over_quota = spend_quota(MODE_QUOTA[mode])
    if over_quota:
        return over_quota

    # Same reason as everything else resolved out here: url_for needs the app
    # context, and Flask has torn it down by the time the generator runs. Called
    # from inside, it raised, the surrounding except swallowed it, and every
    # recording ever made was reported as "could not be recorded". The filename
    # is only known in there, so the prefix is what gets carried in.
    audio_url = url_for('download_audio', filename='')

    system = CHAT_SYSTEM.format(scope=SCOPE,
                                audience=AUDIENCE.get(level, AUDIENCE['Beginner']),
                                wording=WORDING.get(wording, ''))
    system += MODE_SYSTEM.get(mode, '')
    messages = [{'role': 'system', 'content': system}] + turns
    # muse-glimmer everywhere, including prose, which the page-based flows do not
    # do. Measured on this endpoint: muse puts its first word on screen at 4.2 s,
    # nemotron at 17.3 s. Nemotron writes better prose, but seventeen seconds of
    # silence in a chat reads as broken, and the learner can always ask again.
    model = NIM_CODE_MODEL

    # The scratchpad is never forwarded, only the fact that one is being written.
    #
    # Two reasons. It opens by reciting the instructions it was given, so the
    # system prompt would be readable on screen, and filtering that out is a
    # losing game - the model paraphrases ("We need open with everyday analogy")
    # and a paraphrase cannot be matched reliably. And what survives is not worth
    # reading: it is the model talking to itself about formatting rules, not
    # about the subject. A heartbeat gives the same "it is working" signal
    # without either problem.
    def events():
        answer = []
        started = time.monotonic()
        # Sent before the first token so the learner sees which way the question
        # was read, and can change it with the picker if it was read wrongly.
        yield _sse({'type': 'route', 'mode': mode, 'label': MODE_LABEL.get(mode, '')})
        beat = 0.0                           # last heartbeat, seconds since start
        seen_content = False
        try:
            for kind, piece in stream_chat(api_key, messages, model=model):
                if kind == 'thinking':
                    elapsed = time.monotonic() - started
                    # A reasoning model can think for minutes. Rather than leave
                    # the page waiting on a stream that may never turn into an
                    # answer, give up and say so.
                    if not seen_content and elapsed > THINKING_BUDGET:
                        yield _sse({'type': 'error',
                                    'error': 'That took too long to think about. Try asking '
                                             'it in a shorter or more specific way.'})
                        return
                    # One beat a second is enough to keep the page honest about
                    # what is happening, without forwarding the scratchpad.
                    if elapsed - beat >= 1.0:
                        beat = elapsed
                        yield _sse({'type': 'thinking', 'seconds': round(elapsed)})
                else:
                    seen_content = True
                    answer.append(piece)
                    yield _sse({'type': 'content', 'text': piece})
        except Exception as exc:                    # network, HTTP, malformed stream
            logger.error("chat stream failed: %s", exc)
            yield _sse({'type': 'error',
                        'error': 'The model stopped part way. Ask again in a moment.'})
            return

        text = ''.join(answer).strip()
        if not text:
            yield _sse({'type': 'error',
                        'error': 'The model returned nothing. Ask again in a moment.'})
            return

        done = {'type': 'done'}

        if mode == 'code':
            # _extract_code returns (program, prose_without_the_fence). Sending
            # both lets the page swap the raw fence it streamed for a real code
            # block with Copy and Download, the way a chat app renders code.
            if '```' in text:
                program, prose = _extract_code(text)
                done['code'] = program or None
                done['prose'] = prose if program else None
            else:
                done['code'] = None

        elif mode == 'audio':
            yield _sse({'type': 'working', 'label': 'Recording it'})
            try:
                filename = text_to_audio(text, topic or 'lesson')
                if filename:
                    done['audio'] = audio_url + quote(filename)
                    done['audio_name'] = filename
                else:
                    done['note'] = 'The audio could not be recorded, but the script is above.'
            except Exception:
                logger.warning("chat audio failed", exc_info=True)
                done['note'] = 'The audio could not be recorded, but the script is above.'

        elif mode == 'walkthrough':
            # The prose above says what the program is; these two say what each
            # part of it does and what has to be installed for it to run. The
            # packages are read straight off the imports, so they cost nothing
            # and cannot be invented; the sections are a second model call, which
            # is why the page is told what is happening before it starts.
            done['code'] = pasted
            done['packages'] = describe_packages(pasted)
            yield _sse({'type': 'working', 'label': 'Breaking it into sections'})
            try:
                done['sections'] = explain_code_sections(api_key, pasted, topic, wording)
            except Exception:
                logger.warning("chat walkthrough sections failed", exc_info=True)
                done['sections'] = []
            if not done['sections']:
                done['note'] = ('The section-by-section breakdown could not be built for '
                                'this one, but the explanation above still covers it.')

        elif mode == 'images':
            prompts = [line.split('DIAGRAM:', 1)[1].strip()
                       for line in text.splitlines() if 'DIAGRAM:' in line][:3]
            if prompts:
                yield _sse({'type': 'working',
                            'label': 'Drawing %d diagram%s' % (len(prompts),
                                                               '' if len(prompts) == 1 else 's')})
                # generate_images retries per image and can sit for many minutes.
                # A learner would be left on "Drawing 3 diagrams" with no way out
                # but the Stop button, so give it a wall-clock budget. The thread
                # is left to finish on its own; only the waiting is bounded.
                try:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        task = pool.submit(generate_images, prompts, api_key, topic)
                        try:
                            done['images'] = task.result(timeout=IMAGE_BUDGET) or []
                            done['prompts'] = prompts
                        except FuturesTimeout:
                            logger.warning("chat images timed out after %ss", IMAGE_BUDGET)
                            done['note'] = ('The diagrams are taking too long, so here is the '
                                            'explanation on its own. Ask again to retry them.')
                            pool.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    logger.warning("chat images failed", exc_info=True)
                    done['note'] = 'The diagrams could not be drawn, but the explanation is above.'
            else:
                done['note'] = 'No diagrams were suggested for this one.'

        yield _sse(done)

    return Response(events(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',                  # stop a proxy buffering the stream
        'Connection': 'keep-alive',
    })


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
