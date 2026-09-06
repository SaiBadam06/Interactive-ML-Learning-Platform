"""Vercel entrypoint. The Python runtime looks for a WSGI `app` in this module."""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("DATA_DIR", "/tmp")  # only writable path on Vercel

try:
    from app import app  # noqa: E402
except Exception:
    # An import crash surfaces as an opaque FUNCTION_INVOCATION_FAILED with the
    # traceback only in the runtime logs. Always write it to stderr; only serve
    # it to the caller when DEBUG_IMPORT is set, since the traceback exposes
    # paths and a directory listing and this app is public.
    _TRACEBACK = traceback.format_exc()
    sys.stderr.write(_TRACEBACK)

    def app(environ, start_response):  # noqa: F811
        if os.getenv("DEBUG_IMPORT") == "1":
            body = (
                "Import of the Flask app failed during cold start.\n\n"
                f"{_TRACEBACK}\n"
                f"python: {sys.version}\n"
                f"cwd: {os.getcwd()}\n"
                f"listdir(cwd): {sorted(os.listdir(os.getcwd()))[:40]}\n"
            ).encode()
        else:
            body = b"Internal Server Error"
        start_response("500 Internal Server Error",
                       [("Content-Type", "text/plain; charset=utf-8"),
                        ("Content-Length", str(len(body)))])
        return [body]
