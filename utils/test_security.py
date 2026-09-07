"""Regression tests for the auth findings fixed on this branch.

Run: python utils/test_security.py

Each test names the hole it closes. They are cheap and they fail loudly, which
is the point: every one of these was live at some point in this branch's history.
"""

import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADMIN = "admin@example.com"
LEARNER = "learner@example.com"


def build(**env):
    """A fresh app with a specific environment. Reimported so module-level
    configuration (cookie flags, the auth gate) is recomputed each time."""
    # Set to empty rather than removed: app.py calls load_dotenv(), which would
    # otherwise refill them from the developer's real .env and the test would be
    # measuring that file instead of the code.
    for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
                "ADMIN_EMAILS", "AUTH_OPTIONAL", "AUTH_TEST_STUB", "VERCEL",
                "INSECURE_COOKIES", "SITE_URL"):
        os.environ[key] = ""
    os.environ["SECRET_KEY"] = "test-secret-key-not-used-anywhere-real"
    os.environ.update({k: v for k, v in env.items() if v is not None})
    import app as flask_app
    importlib.reload(flask_app)
    return flask_app


def sign_in(client, email):
    with client.session_transaction() as sess:
        sess["user"] = {"id": "11111111-1111-1111-1111-111111111111", "email": email}
        sess["signed_in_at"] = time.time()
        sess["csrf"] = "test-csrf-token"


def test_admin_console_refuses_anonymous_when_login_is_off():
    """`if user and not is_admin(...)` skipped the check entirely when there was
    no user, so the whole account console - and a working CSRF token - was
    served to anyone whenever Supabase was unconfigured."""
    flask_app = build(AUTH_OPTIONAL="1", SUPABASE_SERVICE_ROLE_KEY="sb_secret_fake",
                      ADMIN_EMAILS=ADMIN)
    client = flask_app.app.test_client()
    assert client.get("/admin/users").status_code == 404
    # And the state-changing routes must not merely crash their way to safety.
    assert client.post("/admin/users/delete",
                       json={"user_id": "x", "confirm": "x"}).status_code == 404
    assert client.post("/admin/invite", json={"email": "x@y.com"}).status_code == 404


def test_missing_config_fails_closed_on_any_host():
    """Failing open was previously tied to not being on Vercel, so the
    documented gunicorn deployment published everything if one variable was
    missing."""
    flask_app = build(SUPABASE_SERVICE_ROLE_KEY="sb_secret_fake", ADMIN_EMAILS=ADMIN)
    client = flask_app.app.test_client()
    for path in ("/", "/settings", "/code-generation", "/admin/users"):
        assert client.get(path).status_code == 503, path


def test_auth_optional_never_applies_on_vercel():
    """The dev opt-out must be impossible to switch on in production."""
    flask_app = build(AUTH_OPTIONAL="1", VERCEL="1")
    assert not flask_app.auth.auth_optional()
    assert flask_app.auth.auth_misconfigured_on_vercel()
    assert flask_app.app.test_client().get("/").status_code == 503


def test_non_admin_cannot_reach_the_console():
    flask_app = build(AUTH_OPTIONAL="1", SUPABASE_SERVICE_ROLE_KEY="sb_secret_fake",
                      ADMIN_EMAILS=ADMIN)
    client = flask_app.app.test_client()
    sign_in(client, LEARNER)
    assert client.get("/admin/users").status_code == 404
    sign_in(client, ADMIN)
    assert client.get("/admin/users").status_code == 200


def test_api_requires_csrf():
    """The generation routes spend the deployment's API key, so a cross-site
    post must not be able to trigger one."""
    flask_app = build(AUTH_OPTIONAL="1", ADMIN_EMAILS=ADMIN)
    client = flask_app.app.test_client()
    sign_in(client, LEARNER)

    no_token = client.post("/api/generate-text", json={"topic": "q learning"})
    assert no_token.status_code == 400, no_token.status_code

    wrong = client.post("/api/generate-text", json={"topic": "q learning"},
                        headers={"X-CSRF-Token": "not-the-token"})
    assert wrong.status_code == 400

    # With the right token it gets past the gate (and on to its own validation).
    right = client.post("/api/generate-text", json={"topic": ""},
                        headers={"X-CSRF-Token": "test-csrf-token"})
    assert right.status_code != 400 or b"reload" not in right.data


def test_session_cookie_is_secure_by_default():
    assert build().app.config["SESSION_COOKIE_SECURE"] is True
    assert build(INSECURE_COOKIES="1").app.config["SESSION_COOKIE_SECURE"] is False


def test_generated_filenames_are_unguessable():
    """One shared directory plus a guessable name let any signed-in user fetch
    another learner's generated file."""
    from utils.code_executor import save_code_to_file
    os.makedirs("generated_code", exist_ok=True)
    names = [save_code_to_file("print(1)", "q learning") for _ in range(3)]
    # Minted inside the same second, so anything a stranger could derive from
    # topic and time is identical between them. Only the random part differs.
    assert len(set(names)) == 3, "names collide, so they are predictable"
    for name in names:
        # "q_learning_YYYYmmdd_HHMMSS" is the guessable part; the rest is entropy.
        # token_urlsafe uses "-" and "_" too, so measure rather than split on "_".
        guessable = len("q_learning_20260907_110310")
        assert len(name) - len(".py") - guessable >= 11, name
        os.remove(os.path.join("generated_code", name))


def test_service_key_never_reaches_a_page():
    flask_app = build(AUTH_OPTIONAL="1", SUPABASE_SERVICE_ROLE_KEY="sb_secret_SENTINEL",
                      ADMIN_EMAILS=ADMIN)
    client = flask_app.app.test_client()
    sign_in(client, ADMIN)
    with flask_app.app.test_request_context("/"):
        assert set(flask_app.app_config()) == {"csrf", "supabase_anon_key", "supabase_url"}
    for path in ("/", "/settings", "/admin/users", "/code-generation"):
        assert b"SENTINEL" not in client.get(path).data, path


def test_next_cannot_leave_the_site():
    flask_app = build(AUTH_OPTIONAL="1")
    for hostile in ("//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)",
                    "//evil.com\\@x", "/x\r\nSet-Cookie: a=b", "\thttps://evil.com"):
        assert flask_app.auth.safe_next(hostile) == "/", hostile
    assert flask_app.auth.safe_next("/settings#about") == "/settings#about"


def test_invite_link_target_cannot_be_chosen_by_the_caller():
    """Only the configured site or the current host, never a body value."""
    flask_app = build(AUTH_OPTIONAL="1")
    os.environ["SITE_URL"] = "https://real.example.com"
    try:
        assert flask_app.auth.safe_site_url(
            "https://evil.com", "http://127.0.0.1:5000/") == "https://real.example.com"
        assert flask_app.auth.safe_site_url(
            "here", "http://127.0.0.1:5000/") == "http://127.0.0.1:5000"
    finally:
        os.environ.pop("SITE_URL", None)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("  ok  %s" % name)
            passed += 1
    print("%d security checks passed" % passed)
