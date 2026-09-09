"""Checks for the regex that decides how a dead invite/reset link is explained.

templates/auth_callback.html classifies Supabase's error_code + error text into
"already used or expired" (the common, expected case) versus showing Supabase's
raw message. Read straight out of the template rather than duplicated by hand,
so this cannot drift from what actually ships.
"""
import io
import re

TEMPLATE = "templates/auth_callback.html"


def _pattern():
    """The regex literal on the showDead(...) line, as a compiled Python re."""
    html = io.open(TEMPLATE, encoding="utf-8").read()
    match = re.search(r"showDead\(/(.+?)/i\.test\(errorCode", html)
    assert match, "could not find the classifying regex in " + TEMPLATE
    return re.compile(match.group(1), re.I)


def _is_expiry(error_code, error_description):
    return bool(_pattern().search(error_code + " " + error_description))


def test_a_real_expiry_or_reuse_is_recognised():
    # Supabase's own code for both a timed-out and an already-consumed token.
    assert _is_expiry("otp_expired", "Email link is invalid or has expired")


def test_a_redirect_misconfiguration_is_not_mislabelled_as_expiry():
    """The bug: this used to match on the bare word "invalid" and get shown as
    "already used or expired", hiding that redirect_to is not on Supabase's
    allow-list - a deployment misconfiguration, not a stale link."""
    assert not _is_expiry("access_denied", "Requested path is invalid")


def test_an_unrecognised_error_is_not_swallowed():
    assert not _is_expiry("weird_new_code", "Something Supabase has not said before")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("all invite-link-error checks passed")
