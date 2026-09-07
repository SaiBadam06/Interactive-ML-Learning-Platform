"""Per-account daily generation quota.

Every generation spends the owner's shared NVIDIA free-tier allowance, so one
busy tester can starve everyone else. Usage rows are written server-side with
the secret key (users only have ``select`` under RLS) so nobody can forge or
delete their own usage.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

from utils import auth

logger = logging.getLogger(__name__)

WINDOW = timedelta(hours=24)
TIMEOUT = 10
KINDS = ('text', 'code', 'audio', 'images', 'quiz', 'sections', 'followup')


def daily_limit():
    try:
        return max(0, int(os.getenv('DAILY_GENERATION_LIMIT', '40')))
    except ValueError:
        return 40


def _rest(method, params=None, **kwargs):
    key = auth.service_key()
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key,
               'Content-Type': 'application/json'}
    headers.update(kwargs.pop('headers', {}))
    return requests.request(method, auth.supabase_url() + '/rest/v1/usage_events',
                            headers=headers, params=params, timeout=TIMEOUT, **kwargs)


def _count(header):
    """PostgREST reports the exact count in Content-Range as ``0-24/137``."""
    try:
        return int(str(header).split('/')[-1])
    except (ValueError, AttributeError):
        return None


def _reset_at(user_id, since):
    """When the window frees up: the oldest event in it, plus 24 h."""
    try:
        response = _rest('GET', params={
            'user_id': 'eq.' + user_id, 'created_at': 'gte.' + since,
            'select': 'created_at', 'order': 'created_at.asc', 'limit': '1'})
        rows = response.json()
        oldest = datetime.fromisoformat(rows[0]['created_at'].replace('Z', '+00:00'))
        return oldest + WINDOW
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return datetime.now(timezone.utc) + WINDOW


def check_and_record(user_id, kind, exempt=False):
    """(allowed, remaining, reset_at). ``remaining`` is -1 when unmetered.

    Losing Supabase degrades to "no quota enforcement", never to "app is down":
    any network failure allows the request and logs a warning.
    """
    limit = daily_limit()
    if exempt or not user_id or not auth.invites_enabled() or auth.stub_active():
        return True, -1, None

    since = (datetime.now(timezone.utc) - WINDOW).isoformat()
    try:
        response = _rest('GET',
                         params={'user_id': 'eq.' + user_id, 'created_at': 'gte.' + since,
                                 'select': 'id'},
                         headers={'Prefer': 'count=exact', 'Range': '0-0'})
        used = _count(response.headers.get('Content-Range'))
    except requests.RequestException as e:
        logger.warning("Quota check could not reach Supabase (%s); allowing", type(e).__name__)
        return True, -1, None
    if used is None:
        logger.warning("Quota check returned no count (%s); allowing", response.status_code)
        return True, -1, None

    if used >= limit:
        return False, 0, _reset_at(user_id, since)

    kind = kind if kind in KINDS else 'text'
    try:
        _rest('POST', json={'user_id': user_id, 'kind': kind},
              headers={'Prefer': 'return=minimal'})
    except requests.RequestException as e:
        # The generation is already approved; failing to bill it is not worth
        # denying the learner over.
        logger.warning("Could not record usage (%s)", type(e).__name__)
    return True, limit - used - 1, None


def used_today(user_id):
    """How many generations this account has spent in the window, or None."""
    if not user_id or not auth.invites_enabled():
        return None
    since = (datetime.now(timezone.utc) - WINDOW).isoformat()
    try:
        response = _rest('GET',
                         params={'user_id': 'eq.' + user_id, 'created_at': 'gte.' + since,
                                 'select': 'id'},
                         headers={'Prefer': 'count=exact', 'Range': '0-0'})
        return _count(response.headers.get('Content-Range'))
    except requests.RequestException:
        return None
