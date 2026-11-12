# TI-84 Claude

Ask Claude questions from a TI-84 Plus CE, and later photograph math problems with a
camera built into the case. Built for tinkering and research. Using it on a test
would be cheating.

```
Stage 1 (now):    Calculator --USB--> bridge.py on your computer --HTTPS--> Claude API
Stage 2 (later):  Calculator --link port--> ESP32 + camera in the case --Wi-Fi--> Claude API
```

The calculator never holds the API key. In stage 1 the key lives in `bridge/.env`
on your computer; in stage 2 it is stored on the ESP32.

## What's here

| Folder | What it is | Status |
|---|---|---|
| `bridge/` | Python program that passes questions to Claude and sends back screen-sized answers | Ready to test |
| `calculator/` | C program for the calculator (CE C toolchain) | Not started; waiting on the OS version check |
| `esp32/` | Firmware for the XIAO ESP32S3 Sense with camera | Not started; after the parts arrive |
| `tests/` | Tests for the bridge | 18 passing |

## Step 1: test your API key with the bridge

You need Python 3.10 or newer.

```bash
cd bridge
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Open `bridge/.env` in a text editor and paste your key after `ANTHROPIC_API_KEY=`.
`.env` is in `.gitignore`, so it never gets committed.

Then run:

```bash
python bridge.py --console
```

Type a question and press Enter. The answer is drawn in a box 26 characters wide, the
same width as the calculator screen. To test a photo of a math problem:

```
> photo ~/Desktop/problem.jpg
```

Add `--fast` to use Claude Haiku 5.5, which is quicker and cheaper but less reliable on
hard problems. The default is Claude Opus 5.5.

## Step 2: connect the calculator (coming next)

Once the calculator program exists, plug the calculator into your computer and run:

```bash
python bridge.py --serial COM3            # Windows (check Device Manager for the number)
python bridge.py --serial /dev/ttyACM0    # Linux
python bridge.py --serial /dev/cu.usbmodem1101   # Mac (run ls /dev/cu.* to find it)
```

### Serial protocol

Plain ASCII, one message per line ending in `\n`.

| Direction | Message | Meaning |
|---|---|---|
| calculator to bridge | `Q:<question>` | Ask a question |
| calculator to bridge | `PING` | Check the bridge is running |
| bridge to calculator | `A:<line>` | One screen line of the answer (26 characters max) |
| bridge to calculator | `E:<message>` | An error to show on screen |
| bridge to calculator | `PONG` | Reply to `PING` |
| bridge to calculator | `END` | The reply is complete |

## Running the tests

```bash
pip install pytest
python -m pytest
```

The tests use a fake Claude client, so they don't need an API key or cost anything.
