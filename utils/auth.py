"""Supabase-backed login for the Flask app.

Supabase Auth owns identity; Flask keeps its own signed cookie so the AI routes
never trust a token they did not verify. Verification is one HTTP call to
Supabase's ``/auth/v1/user`` - no JWT library, and keys are treated as opaque
strings (this project uses the new ``sb_publishable_`` / ``sb_secret_`` keys,
which are not JWTs at all).
"""
import hmac
import logging
import os
import re
import secrets
import time
import uuid
from collections import OrderedDict
from functools import wraps

import requests
from flask import abort, jsonify, redirect, render_template_string, request, session, url_for

logger = logging.getLogger(__name__)

SESSION_HOURS = 12
VERIFY_TIMEOUT = 10
# Case 15: how long a "does this user still exist" answer may be reused.
EXISTS_TTL = 60
EXISTS_MAX = 500

STUB_USER = {'id': '00000000-0000-0000-0000-000000000001', 'email': 'test@example.com'}
STUB_TOKEN = 'test-token'


# ---------------------------------------------------------------- configuration

def _env(name):
    return (os.getenv(name) or '').strip()


def supabase_url():
    return _env('SUPABASE_URL').rstrip('/')


def anon_key():
    return _env('SUPABASE_ANON_KEY')


def service_key():
    """Server-only secret key. Never put this in a template, a log or a response."""
    return _env('SUPABASE_SERVICE_ROLE_KEY')


def admin_emails():
    return {e.strip().lower() for e in _env('ADMIN_EMAILS').split(',') if e.strip()}


def on_vercel():
    return bool(_env('VERCEL'))


def auth_optional():
    """Explicit opt-out for local development and the test suite.

    Running without login used to be the automatic consequence of Supabase
    being unset, which meant a typo in one variable silently published the
    whole app - including the admin console. It now has to be asked for, and
    can never be asked for on a deployment.
    """
    return bool(_env('AUTH_OPTIONAL')) and not on_vercel()


def stub_active():
    """The e2e stub. Refuses to activate on Vercel - it would be a login bypass."""
    return bool(_env('AUTH_TEST_STUB')) and not on_vercel()


def missing_config():
    """Which of the three required variables are absent."""
    return [name for name in ('SUPABASE_URL', 'SUPABASE_ANON_KEY', 'SECRET_KEY') if not _env(name)]


def auth_enabled():
    """Whether login is enforced. Off locally when Supabase is not configured, so
    development and the existing test suite keep working without an account."""
    return stub_active() or bool(supabase_url() and anon_key()) or not auth_optional()


def auth_misconfigured_on_vercel():
    """Fail closed: configured for login but missing a variable means nobody
    gets in, on any host. Only an explicit AUTH_OPTIONAL off Vercel opts out."""
    return bool(missing_config()) and not auth_optional()


def invites_enabled():
    return bool(supabase_url() and service_key())


def is_admin(email):
    return bool(email) and str(email).strip().lower() in admin_emails()


def safe_site_url(choice, host_url):
    """Base URL an invite link comes back to.

    Only two values are ever possible - the configured SITE_URL or the host this
    request arrived on - because both are what the Supabase redirect allow-list
    contains. Taking a URL from the request body would let an admin aim a live
    invite at any domain they like.
    """
    here = str(host_url or '/').rstrip('/')
    site = _env('SITE_URL').rstrip('/')
    return here if (str(choice or '') == 'here' or not site) else site


# ------------------------------------------------------------------- safe_next

def safe_next(value):
    """A relative in-app path, or ``/``. Blocks scheme, protocol-relative and
    backslash tricks that would turn ?next= into an open redirect."""
    value = (value or '').strip()
    if (not value.startswith('/') or value.startswith('//') or '\\' in value
            or '://' in value or any(c in value for c in '\r\n\t')):
        return '/'
    return value[:500]


# ------------------------------------------------------------------------ CSRF

def csrf_token():
    """The session's CSRF token, minting one on first use."""
    token = session.get('csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf'] = token
    return token


def csrf_ok():
    sent = request.headers.get('X-CSRF-Token') or (request.form.get('csrf_token') or '')
    held = session.get('csrf') or ''
    return bool(sent) and bool(held) and hmac.compare_digest(sent, held)


# ------------------------------------------------------------------ rate limits
# ponytail: in-process counters. Per instance, so a horizontally scaled deploy
# multiplies the limit by the instance count; swap for a shared store if that
# ever matters. Good enough to stop a script, which is all this is for.
_HITS = {}


def rate_limit(bucket, key, limit, window):
    """(allowed, retry_after_seconds). Records the hit when allowed."""
    now = time.time()
    hits = _HITS.setdefault((bucket, key), [])
    cutoff = now - window
    while hits and hits[0] <= cutoff:
        hits.pop(0)
    if len(hits) >= limit:
        return False, int(hits[0] + window - now) + 1
    hits.append(now)
    return True, 0


def reset_rate_limits():
    _HITS.clear()


# ------------------------------------------------------------------ Supabase IO

def admin_request(method, path, **kwargs):
    """Call a Supabase Auth admin endpoint with the secret key.

    Both headers are required: the new-style secret key goes in ``apikey`` and
    in ``Authorization``. Raises ``requests.RequestException`` on network trouble.
    """
    key = service_key()
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key,
               'Content-Type': 'application/json'}
    kwargs.setdefault('timeout', VERIFY_TIMEOUT)
    return requests.request(method, supabase_url() + '/auth/v1' + path, headers=headers, **kwargs)


def verify_token(access_token):
    """{'id', 'email'} if Supabase vouches for this token, else None."""
    if not access_token:
        return None
    if stub_active():
        return dict(STUB_USER) if access_token == STUB_TOKEN else None
    try:
        response = requests.get(
            supabase_url() + '/auth/v1/user',
            headers={'apikey': anon_key(), 'Authorization': 'Bearer ' + access_token},
            timeout=VERIFY_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning("Token verification could not reach Supabase: %s", type(e).__name__)
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict) or not data.get('id') or not data.get('email'):
        return None
    return {'id': str(data['id']), 'email': str(data['email']).strip().lower()}


_EXISTS = OrderedDict()


def forget_user(user_id):
    _EXISTS.pop(user_id, None)


def user_exists(user_id):
    """True / False / None where None means "could not tell".

    Case 15: a deleted user's Flask cookie stays cryptographically valid for 12
    hours, so every request re-checks the account - memoised for a minute per
    user so it costs at most one extra call per user per minute.
    """
    if stub_active():
        return True
    if not invites_enabled():
        return None
    now = time.time()
    cached = _EXISTS.get(user_id)
    if cached and now - cached[0] < EXISTS_TTL:
        return cached[1]
    try:
        response = admin_request('GET', '/admin/users/' + user_id)
    except requests.RequestException as e:
        logger.warning("Could not check account status: %s", type(e).__name__)
        return None
    if response.status_code == 404:
        exists = False
    elif response.status_code == 200:
        exists = True
    else:
        logger.warning("Unexpected status checking account: %s", response.status_code)
        return None
    _EXISTS[user_id] = (now, exists)
    _EXISTS.move_to_end(user_id)
    while len(_EXISTS) > EXISTS_MAX:
        _EXISTS.popitem(last=False)
    return exists


# ------------------------------------------------------------------ the gate

_NOT_CONFIGURED = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Login is not configured</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,sans-serif;margin:0;display:grid;place-items:center;min-height:100vh;
background:#0f172a;color:#e2e8f0}main{max-width:34rem;padding:2rem;text-align:center}
code{background:#1e293b;padding:.15rem .4rem;border-radius:.25rem}</style></head>
<body><main><h1>Login is not configured</h1>
<p>This deployment is missing {{ missing }}. Set it in the project's environment
variables and redeploy.</p></main></body></html>"""


def not_configured_response():
    names = ', '.join(missing_config())
    return render_template_string(_NOT_CONFIGURED, missing=names), 503


def current_user():
    return session.get('user') or None


def wants_json():
    return request.path.startswith('/api/')


def guard():
    """None if the request may proceed, otherwise the response to send instead."""
    if auth_misconfigured_on_vercel():
        return not_configured_response()
    if not auth_enabled():
        return None
    user = current_user()
    if user and user_exists(user.get('id')) is False:
        logger.info("Session for a deleted account was rejected")
        session.clear()
        user = None
    if user:
        return None
    if wants_json():
        return jsonify({'error': 'Not signed in', 'login': '/login'}), 401
    target = request.path
    if request.query_string:
        target += '?' + request.query_string.decode('utf-8', 'ignore')
    return redirect(url_for('login', next=safe_next(target)))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        blocked = guard()
        return blocked if blocked is not None else view(*args, **kwargs)
    return wrapper


def admin_required(view):
    """404 rather than 403: the admin pages should not advertise their existence."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        blocked = guard()
        if blocked is not None:
            return blocked
        user = current_user()
        # `user and ...` let an anonymous caller through whenever login was
        # disabled: no session means no user, so the check simply did not run.
        if not user or not is_admin(user.get('email')):
            abort(404)  # identical to a page that does not exist
        return view(*args, **kwargs)
    return wrapper


# ------------------------------------------------------------------- validation

_EMAIL = re.compile(r'^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)+$')


def valid_email(value):
    value = (value or '').strip()
    return bool(value) and len(value) <= 254 and bool(_EMAIL.match(value))


def valid_uuid(value):
    """Supabase answers 404 (not 400) for a malformed id, which would be
    reported to the admin as "no such user". Reject it here instead."""
    try:
        uuid.UUID(str(value or '').strip())
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def sign_in(user):
    """Replace whatever session exists with a fresh logged-in one."""
    session.clear()
    session['user'] = {'id': user['id'], 'email': user['email']}
    session['login_at'] = int(time.time())
    session['csrf'] = secrets.token_urlsafe(32)
    session.permanent = True
    forget_user(user['id'])
