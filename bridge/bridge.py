"""USB bridge between a TI-84 Plus CE and Claude.

Two ways to run it:

  python bridge.py --console          Type questions here to test your key.
                                      Type "photo path/to/problem.jpg" to
                                      test a photo of a math problem.
  python bridge.py --serial PORT      Talk to the calculator over USB.

Add --fast to use the faster, cheaper model.

Serial protocol (plain ASCII, one message per line ending in \\n):
  calculator -> bridge   Q:<question>      ask a question
                         PING              check the bridge is there
  bridge -> calculator   A:<line>          one screen line of the answer
                         E:<message>       an error to show
                         PONG              reply to PING
                         END               the reply is complete
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from calc_text import SCREEN_WIDTH, to_screen_lines
from claude_client import Claude, ClaudeError

# Longest question line the bridge will accept from the calculator.
MAX_QUESTION = 500

# Messages only the dongle can answer (camera and Wi-Fi setup).
DONGLE_ONLY = {"VIEW", "SNAP", "PHOTO", "SCAN", "SAVED", "CREDIT"}


def handle_line(line: str, claude: Claude, width: int = SCREEN_WIDTH) -> list[str]:
    """Answer one protocol message from the calculator with reply lines."""
    line = line.strip()
    if line == "PING":
        return ["PONG"]
    if line == "STATUS":
        return [f"S:{text}" for text in to_screen_lines(
            f"Connected to the bridge on your computer. Model: {claude.model}", width)] + ["END"]
    if line in DONGLE_ONLY or line.startswith(("PHOTO:", "WIFI:", "JOIN:", "FORGET:", "CREDIT:")):
        return ["E:Only the dongle can do", "E:that. The bridge has no", "E:camera or Wi-Fi setup.", "END"]
    if not line.startswith("Q:"):
        return ["E:Unknown message.", "END"]
    question = line[2:].strip()[:MAX_QUESTION]
    if not question:
        return ["E:Type a question first.", "END"]
    try:
        answer = claude.ask(question)
    except ClaudeError as exc:
        return [f"E:{msg}" for msg in to_screen_lines(str(exc), width)] + ["END"]
    return [f"A:{text}" for text in to_screen_lines(answer, width)] + ["END"]


def run_console(claude: Claude, width: int) -> None:
    print(f"Using {claude.model}. Answers are wrapped to {width} characters.")
    print('Type a question, "photo path/to/image.jpg", or "quit".')
    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.lower() in {"quit", "exit"}:
            return
        try:
            if line.lower().startswith("photo "):
                path = Path(line[6:].strip().strip('"')).expanduser()
                if not path.is_file():
                    print(f"No file at {path}")
                    continue
                answer = claude.ask(image_bytes=path.read_bytes())
            else:
                answer = claude.ask(line)
        except ClaudeError as exc:
            print(f"Error: {exc}")
            continue
        print("+" + "-" * width + "+")
        for screen_line in to_screen_lines(answer, width):
            print("|" + screen_line.ljust(width) + "|")
        print("+" + "-" * width + "+")


def run_serial(claude: Claude, port: str, width: int) -> None:
    import serial  # pyserial

    print(f"Using {claude.model}. Waiting for the calculator on {port}...")
    with serial.Serial(port, 115200, timeout=None) as conn:
        while True:
            raw = conn.readline()
            if not raw:
                continue
            line = raw.decode("ascii", "replace")
            print(f"calc> {line.strip()}")
            for reply in handle_line(line, claude, width):
                conn.write((reply + "\n").encode("ascii", "replace"))
            conn.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--console", action="store_true", help="test from the keyboard")
    mode.add_argument("--serial", metavar="PORT", help="calculator port, e.g. COM3 or /dev/ttyACM0")
    parser.add_argument("--fast", action="store_true", help="use the faster, cheaper model")
    parser.add_argument("--width", type=int, default=SCREEN_WIDTH, help="screen width in characters")
    args = parser.parse_args()

    load_dotenv(Path(__file__).with_name(".env"))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("No API key found. Copy .env.example to .env and paste your key into it.")
        return 1

    claude = Claude(speed="fast" if args.fast else "best")
    if args.console:
        run_console(claude, args.width)
    else:
        run_serial(claude, args.serial, args.width)
    return 0


if __name__ == "__main__":
    sys.exit(main())
