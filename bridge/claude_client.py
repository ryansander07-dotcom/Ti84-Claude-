"""Ask Claude a question, optionally with a photo, and get a short answer."""

import base64
import io

import anthropic

MODELS = {
    "best": "claude-opus-5-5",
    "fast": "claude-haiku-5-5",
}

SYSTEM_PROMPT = """\
You answer questions for a student using a TI-84 Plus CE graphing calculator.
Your reply is shown on its small screen, 26 characters wide and 10 lines tall,
so the student scrolls to read it.

Rules for every reply:
- Plain ASCII text only. No Markdown, no LaTeX, no emoji, no Unicode symbols.
- Write math the way you would type it on the calculator: x^2, sqrt(x),
  (a+b)/(c+d), pi, 3*x, <=, >=.
- Keep it short. For a math problem, give the key steps on separate lines,
  one step per line, then a last line that starts with "ANSWER:".
- For anything else, answer in at most 6 short sentences.
- If a photo is unreadable or cut off, say what you can read and ask for a
  clearer photo instead of guessing.
"""

PHOTO_PROMPT = "Solve the math problem in this photo."

# Claude reads images best at about 1568 pixels on the long side, and
# smaller photos upload faster over the ESP32's Wi-Fi.
MAX_IMAGE_EDGE = 1568


class ClaudeError(Exception):
    """A problem worth showing on the calculator screen."""


def prepare_image(image_bytes: bytes) -> tuple[str, str]:
    """Shrink and re-encode a photo as JPEG. Returns (media_type, base64)."""
    from PIL import Image, ImageOps

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
    except Exception as exc:  # Pillow raises several error types here
        raise ClaudeError("Could not read that image file.") from exc
    image = image.convert("RGB")
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return "image/jpeg", base64.standard_b64encode(out.getvalue()).decode("ascii")


class Claude:
    def __init__(self, speed: str = "best", client: anthropic.Anthropic | None = None):
        if speed not in MODELS:
            raise ValueError(f"speed must be one of {sorted(MODELS)}")
        self.model = MODELS[speed]
        self.client = client or anthropic.Anthropic()

    def ask(self, question: str = "", image_bytes: bytes | None = None) -> str:
        content: list[dict] = []
        if image_bytes is not None:
            media_type, data = prepare_image(image_bytes)
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                }
            )
        content.append({"type": "text", "text": question.strip() or PHOTO_PROMPT})

        request = {
            "model": self.model,
            "max_tokens": 16000,
            "system": SYSTEM_PROMPT,
            "output_config": {"effort": "medium"},
            "messages": [{"role": "user", "content": content}],
        }

        try:
            if self.model == MODELS["best"]:
                # If Opus declines on a safety false positive, the API retries
                # the same request on a fallback model inside the same call.
                response = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    **request,
                )
            else:
                response = self.client.messages.create(**request)
        except anthropic.AuthenticationError as exc:
            raise ClaudeError("API key not accepted. Check the .env file.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ClaudeError("API key can't use this model or has no credit.") from exc
        except anthropic.RateLimitError as exc:
            raise ClaudeError("Too many requests. Wait a minute and try again.") from exc
        except anthropic.APIStatusError as exc:
            raise ClaudeError(f"Claude API error {exc.status_code}. Try again.") from exc
        except anthropic.APIConnectionError as exc:
            raise ClaudeError("No internet connection.") from exc

        if response.stop_reason == "refusal":
            raise ClaudeError("Claude declined to answer that one.")

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise ClaudeError("Claude sent back an empty answer. Try again.")
        if response.stop_reason == "max_tokens":
            text += "\n(answer cut off)"
        return text
