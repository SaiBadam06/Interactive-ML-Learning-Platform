"""Vercel entrypoint. The Python runtime looks for a WSGI `app` in this module."""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("DATA_DIR", "/tmp")  # only writable path on Vercel

try:
    from app import app  # noqa: E402
except Exception:
    # A crash while importing shows up as an opaque FUNCTION_INVOCATION_FAILED
    # with the traceback only in the runtime logs. Serve it instead so the cause
    # is visible from a plain request. Remove once the deployment is healthy.
    _TRACEBACK = traceback.format_exc()
    sys.stderr.write(_TRACEBACK)

    def app(environ, start_response):  # noqa: F811
        body = (
            "Import of the Flask app failed during cold start.\n\n"
            f"{_TRACEBACK}\n"
            f"sys.path: {sys.path}\n"
            f"cwd: {os.getcwd()}\n"
            f"listdir(cwd): {sorted(os.listdir(os.getcwd()))[:40]}\n"
        ).encode()
        start_response("500 Internal Server Error",
                       [("Content-Type", "text/plain; charset=utf-8"),
                        ("Content-Length", str(len(body)))])
        return [body]
