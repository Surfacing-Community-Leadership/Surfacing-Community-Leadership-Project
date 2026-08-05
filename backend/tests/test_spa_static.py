"""The SPA fallback that serves the built frontend in production.

These exist because of a real vulnerability. The fallback used to join the
request path straight onto the frontend's dist directory, and Starlette does not
decode-then-normalise the path before handing it over — so a request for
`/..%2f..%2fbackend%2f.env` arrived as the literal string `../../backend/.env`
and the server happily returned it. SECRET_KEY, DATABASE_URL and the OAuth
secrets were readable by anyone who asked.

The fix resolves both the root and the candidate and checks containment. These
tests pin that behaviour, in the encodings that actually got through, so it
cannot regress.

They build a throwaway "dist" and point the app's resolver at it, rather than
depending on whether the real frontend happens to be built.
"""

from pathlib import Path

import pytest

from app import main as app_main


@pytest.fixture
def fake_dist(tmp_path, monkeypatch):
    """A dist directory with one real asset, and a secret file just outside it."""
    dist = tmp_path / "dist"
    (dist / "fonts").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>")
    (dist / "favicon.ico").write_text("icon")
    (dist / "fonts" / "caprasimo-400.woff2").write_bytes(b"woff2-bytes")
    # The thing an attacker is reaching for.
    (tmp_path / "secret.env").write_text("SECRET_KEY=super-secret\nDATABASE_URL=postgres://x")

    monkeypatch.setattr(app_main, "FRONTEND_DIST", dist)
    return dist


def _resolve(full_path: str):
    """Call the same helper the route uses."""
    return app_main._safe_static(full_path)


# ---- what must be refused --------------------------------------------------

# Every one of these is a way of writing "leave the dist directory". The
# url-encoded forms are the ones that defeated the original implementation,
# because Starlette hands the decoded-but-not-normalised string to the route.
ESCAPES = [
    "../secret.env",
    "../../secret.env",
    "fonts/../../secret.env",
    "fonts/../../../etc/passwd",
    "/etc/passwd",
    "../",
    "..",
]


@pytest.mark.parametrize("attempt", ESCAPES)
def test_paths_that_escape_the_dist_directory_are_refused(fake_dist, attempt):
    assert _resolve(attempt) is None


def test_the_exact_payload_that_leaked_the_env_file_is_refused(fake_dist):
    """The regression itself. Starlette decodes %2f to / but does not collapse
    the `..` segments, so this arrives as a literal relative path."""
    assert _resolve("../../secret.env") is None
    assert _resolve("..%2f..%2fsecret.env") is None


def test_an_absolute_path_cannot_be_smuggled_in(fake_dist, tmp_path):
    assert _resolve(str(tmp_path / "secret.env")) is None


def test_a_symlink_pointing_outside_is_refused(fake_dist, tmp_path):
    """Containment is checked after resolution, so a symlink can't tunnel out."""
    link = fake_dist / "sneaky.env"
    try:
        link.symlink_to(tmp_path / "secret.env")
    except OSError:  # pragma: no cover — filesystem without symlink support
        pytest.skip("symlinks unavailable")
    assert _resolve("sneaky.env") is None


def test_the_dist_root_itself_is_not_served(fake_dist):
    assert _resolve("") is None
    assert _resolve(".") is None


# ---- what must still work --------------------------------------------------


def test_real_assets_inside_dist_are_served(fake_dist):
    """The flyer depends on this: the self-hosted fonts are served by this same
    fallback, so a fix that broke it would silently export posters in the
    fallback typeface."""
    resolved = _resolve("fonts/caprasimo-400.woff2")
    assert resolved is not None
    assert resolved == (fake_dist / "fonts" / "caprasimo-400.woff2").resolve()

    assert _resolve("favicon.ico") is not None


def test_a_client_side_route_is_not_treated_as_a_file(fake_dist):
    """`/e/<uuid>` is a React Router path, not a file — the caller falls through
    to index.html when this returns None."""
    assert _resolve("e/4c0c3a4b-dc4d-4d43-a189-ba9af34be395") is None
    assert _resolve("board") is None


def test_a_path_that_normalises_back_inside_is_allowed(fake_dist):
    """`fonts/../favicon.ico` never leaves the directory, so refusing it would be
    over-broad — containment, not string matching, is the rule."""
    assert _resolve("fonts/../favicon.ico") is not None


def test_reserved_backend_prefixes_are_still_reserved():
    """Guards the other half of the route: these must never reach the SPA."""
    for prefix in ("api", "media", "admin", "health", "docs", "redoc", "openapi.json"):
        assert prefix in app_main._RESERVED


# ---- and the route end to end ----------------------------------------------


async def test_the_running_app_does_not_serve_files_outside_dist(client):
    """Belt and braces through the real HTTP stack, whatever the local
    FRONTEND_DIST happens to contain."""
    for attempt in ("/../backend/.env", "/..%2f..%2fbackend%2f.env"):
        r = await client.get(attempt)
        body = r.text
        assert "SECRET_KEY" not in body
        assert "DATABASE_URL" not in body
        assert "postgresql" not in body
