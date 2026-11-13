import io
import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))

from bridge import handle_line  # noqa: E402
from calc_text import SCREEN_WIDTH, to_ascii, to_screen_lines  # noqa: E402
from claude_client import MODELS, Claude, ClaudeError, prepare_image  # noqa: E402


# --- calc_text -------------------------------------------------------------

def test_symbols_become_ascii():
    assert to_ascii("x² − 4 ≤ π × 3") == "x^2 - 4 <= pi * 3"


def test_markdown_is_stripped():
    text = "## Steps\n**Subtract 6:** `2x = 8`\n* Divide by 2"
    assert to_ascii(text) == "Steps\nSubtract 6: 2x = 8\n- Divide by 2"


def test_latex_is_rewritten():
    assert to_ascii(r"\(\frac{x+1}{2} \leq \sqrt{9}\)") == "(x+1)/(2) <= sqrt(9)"
    assert to_ascii(r"$x^{10} \cdot \pi$") == "x^(10) * pi"
    assert to_ascii(r"\frac{\frac{1}{2}}{3}") == "((1)/(2))/(3)"


def test_unknown_unicode_becomes_question_mark():
    assert to_ascii("café ☃") == "caf? ?"


def test_lines_fit_the_screen():
    long = "Subtract six from both sides of the equation to isolate the term with x"
    lines = to_screen_lines(long + "\n\nANSWER: x = 4")
    assert all(len(line) <= SCREEN_WIDTH for line in lines)
    assert "" in lines  # paragraph break kept
    assert lines[-1] == "ANSWER: x = 4"


def test_very_long_word_is_split():
    lines = to_screen_lines("a" * 60)
    assert lines == ["a" * 26, "a" * 26, "a" * 8]


# --- serial protocol -------------------------------------------------------

class FakeClaude:
    def __init__(self, answer="Subtract 6: 2x = 8\nANSWER: x = 4", error=None):
        self.answer, self.error, self.questions = answer, error, []

    def ask(self, question="", image_bytes=None):
        self.questions.append(question)
        if self.error:
            raise ClaudeError(self.error)
        return self.answer


def test_ping():
    assert handle_line("PING\n", FakeClaude()) == ["PONG"]


def test_question_is_answered_in_screen_lines():
    claude = FakeClaude()
    assert handle_line("Q:2X+6=14\n", claude) == [
        "A:Subtract 6: 2x = 8",
        "A:ANSWER: x = 4",
        "END",
    ]
    assert claude.questions == ["2X+6=14"]


def test_empty_question_and_unknown_message():
    assert handle_line("Q:   \n", FakeClaude()) == ["E:Type a question first.", "END"]
    assert handle_line("HELLO\n", FakeClaude()) == ["E:Unknown message.", "END"]


def test_status_reports_the_bridge():
    claude = FakeClaude()
    claude.model = "claude-opus-5-5"
    reply = handle_line("STATUS\n", claude)
    assert reply[-1] == "END"
    assert all(r.startswith("S:") and len(r) - 2 <= SCREEN_WIDTH for r in reply[:-1])
    assert "claude-opus-5-5" in "".join(r[2:] for r in reply[:-1])


def test_dongle_only_messages_get_an_error():
    for msg in ["VIEW", "SNAP", "PHOTO", "PHOTO:part b", "SCAN", "WIFI:home\tsecret", "SAVED", "JOIN:home", "FORGET:home", "CREDIT", "CREDIT:4.95"]:
        reply = handle_line(msg + "\n", FakeClaude())
        assert reply[0].startswith("E:") and reply[-1] == "END", msg
        assert all(len(r) - 2 <= SCREEN_WIDTH for r in reply[:-1])


def test_errors_are_wrapped_for_the_screen():
    reply = handle_line("Q:hi", FakeClaude(error="API key not accepted. Check the .env file."))
    assert reply[-1] == "END"
    assert all(r.startswith("E:") and len(r) - 2 <= SCREEN_WIDTH for r in reply[:-1])


def test_long_question_is_truncated():
    claude = FakeClaude()
    handle_line("Q:" + "x" * 2000, claude)
    assert len(claude.questions[0]) == 500


# --- Claude client ---------------------------------------------------------

def _response(text="ANSWER: 4", stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
    )


class FakeMessages:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response or _response(), exc, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.response


def _fake_client(**kwargs):
    beta = FakeMessages(**kwargs)
    plain = FakeMessages(**kwargs)
    client = SimpleNamespace(messages=plain, beta=SimpleNamespace(messages=beta))
    return client, beta, plain


def _jpeg(size=(3000, 2000)):
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


def test_best_model_uses_opus_with_fallbacks():
    client, beta, plain = _fake_client()
    assert Claude("best", client).ask("2+2?") == "ANSWER: 4"
    call = beta.calls[0]
    assert call["model"] == MODELS["best"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["messages"][0]["content"] == [{"type": "text", "text": "2+2?"}]
    assert not plain.calls


def test_fast_model_uses_haiku_without_fallbacks():
    client, beta, plain = _fake_client()
    Claude("fast", client).ask("2+2?")
    assert plain.calls[0]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in plain.calls[0]
    assert not beta.calls


def test_photo_is_resized_and_sent_before_the_prompt():
    client, beta, _ = _fake_client()
    Claude("best", client).ask(image_bytes=_jpeg())
    content = beta.calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[1] == {"type": "text", "text": "Solve the math problem in this photo."}
    media_type, data = prepare_image(_jpeg())
    import base64
    img = Image.open(io.BytesIO(base64.b64decode(data)))
    assert max(img.size) == 1568


def test_bad_image_gives_a_readable_error():
    with pytest.raises(ClaudeError, match="Could not read"):
        prepare_image(b"not an image")


def test_refusal_and_cutoff():
    client, *_ = _fake_client(response=_response(stop_reason="refusal"))
    with pytest.raises(ClaudeError, match="declined"):
        Claude("best", client).ask("hi")
    client, *_ = _fake_client(response=_response("Step 1", stop_reason="max_tokens"))
    assert Claude("best", client).ask("hi").endswith("(answer cut off)")


def test_auth_error_mentions_the_env_file():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.AuthenticationError(
        "bad key", response=httpx2.Response(401, request=request), body=None
    )
    client, *_ = _fake_client(exc=exc)
    with pytest.raises(ClaudeError, match=r"\.env"):
        Claude("best", client).ask("hi")


def test_no_connection():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client, *_ = _fake_client(exc=anthropic.APIConnectionError(request=request))
    with pytest.raises(ClaudeError, match="internet"):
        Claude("best", client).ask("hi")
