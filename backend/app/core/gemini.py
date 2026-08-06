"""The one place in the app that talks to Gemini.

Both features that use the model — the flyer's copy and the guide's questions —
want the same thing: a JSON object, quickly, or a clean failure. They used to
each build their own client and config, which meant a problem with the call had
to be found and fixed twice. It was: see the note on thinking below.

The key is read from settings here and nowhere else. It never leaves the server.
"""

import logging

from app.core.config import settings

log = logging.getLogger("ours.gemini")


class GeminiError(Exception):
    """The model could not be reached, or returned something unusable.

    Callers decide what that means for the person in front of them: the flyer
    falls back to templated copy, the guide reports itself unavailable.
    """


class GeminiBusy(GeminiError):
    """Rate-limited upstream — the same request would work shortly.

    Worth its own type because on the free tier this is not an edge case, it is
    the *expected* failure: the per-minute request quota is shared by the whole
    project, and a single guided conversation is four to six calls. "Try again
    in a moment" is true and actionable; "unavailable" would send somebody away
    from a feature that is about to work.
    """


def _wrap(exc: Exception) -> GeminiError:
    """Every upstream failure becomes one of ours, so callers never have to
    import the SDK's exception types to tell one from another."""
    text = str(exc)
    kind = GeminiBusy if ("RESOURCE_EXHAUSTED" in text or "429" in text) else GeminiError
    return kind(f"{type(exc).__name__}: {exc}")


# Room for the answer AND for whatever the model does before it answers.
#
# This number is the fix for a real bug. `gemini-flash-latest` is a thinking
# model, and thinking tokens are spent from the same allowance as the reply. At
# 800 tokens a trivial prompt burned 445 of them on thoughts and the JSON came
# back cut off mid-string — which looked, from the outside, exactly like the
# model returning garbage. Generous headroom means thinking can't starve the
# answer even when the alias moves to a model that thinks harder.
DEFAULT_MAX_OUTPUT_TOKENS = 3000


async def generate_json(
    prompt: str,
    *,
    temperature: float,
    timeout_seconds: int,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> str:
    """The model's reply as raw JSON text. Raises GeminiError, never returns junk.

    Parsing is the caller's job — what a valid reply looks like differs between
    a flyer and a conversation, and this layer has no business knowing.
    """
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is unset")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)

    def build(**extra):
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            # A hard server-side deadline in milliseconds, so a hanging call
            # can't hold a request open indefinitely.
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
            **extra,
        )

    # Neither of these tasks is reasoning; both are "rewrite what you were
    # given, in this shape". Asking for minimal thinking makes them faster and
    # much cheaper against a per-minute token quota.
    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=build(thinking_config=types.ThinkingConfig(thinking_level="low")),
        )
    except Exception as exc:
        # Not every model accepts a thinking level, and the alias in settings is
        # deliberately not pinned — so a model that rejects the parameter must
        # not take the feature down with it. One retry without it, on the
        # generous token budget that made thinking survivable in the first place.
        if "INVALID_ARGUMENT" not in str(exc):
            raise _wrap(exc)
        log.info("gemini: %s rejected thinking_level — retrying without it",
                 settings.gemini_model)
        try:
            response = await client.aio.models.generate_content(
                model=settings.gemini_model, contents=prompt, config=build()
            )
        except Exception as retry_exc:
            raise _wrap(retry_exc) from retry_exc

    # A truncated reply is unparseable JSON, which without this reads as "the
    # model returned garbage" when the real cause is a token ceiling — the
    # difference between a five-minute fix and an afternoon.
    candidate = (response.candidates or [None])[0]
    finish = getattr(candidate, "finish_reason", None)
    if finish is not None and str(finish).endswith("MAX_TOKENS"):
        raise GeminiError(
            f"reply truncated at max_output_tokens={max_output_tokens}"
        )

    text = response.text or ""
    if not text.strip():
        raise GeminiError(f"empty reply (finish_reason={finish})")
    return text
