# TI-84 Claude

Ask Claude questions from a TI-84 Plus CE, and photograph math problems, using a small
plug-in dongle. Built for tinkering and research. Using it on a test would be cheating.

```
Goal:     Calculator --USB OTG cable--> dongle (ESP32-S3 + camera) --Wi-Fi--> Claude API
Testing:  Calculator --USB cable------> bridge.py on your computer  --HTTPS--> Claude API
```

The calculator never holds the API key. On the dongle it is stored in the firmware; with
the test bridge it lives in `bridge/.env` on your computer.

## How the dongle works

The dongle has no buttons and no screen. You set it up once from your computer, then
you only ever plug it into the calculator. Everything is done from the calculator:

- **Ask**: type a question and the answer scrolls on screen.
- **Photo**: the calculator shows a live preview from the dongle's camera so you can
  aim it. Press Enter to take the picture; the dongle sends it to Claude and the
  answer comes back to the calculator.
- **Wi-Fi**: pick a network and type its password on the calculator. The dongle saves
  it and remembers it.
- **Status**: shows whether the dongle is connected to Wi-Fi and to Claude.

One-time setup: put your API key (and, optionally, your home Wi-Fi) in
`esp32/secrets.h`, then flash the dongle from your computer over USB-C. `secrets.h` is in
`.gitignore`, so it never gets committed.

**Hardware**

- An ESP32-S3 camera board with native USB and PSRAM: the Seeed XIAO ESP32S3 Sense
  (best documented) or the Meshnology W11 ESP32-S3 with OV3660.
- A USB OTG cable, mini-USB (male) to USB-C (male). It must be OTG so the calculator
  acts as the USB host and powers the dongle.
- Optional: a small 3.7 V LiPo (400-500 mAh) on the board's battery pads, if the
  calculator's USB port can't supply enough power for Wi-Fi.

## What's here

| Folder | What it is | Status |
|---|---|---|
| `bridge/` | Python program that stands in for the dongle on your computer, for testing | Ready to test |
| `calculator/` | C program for the calculator (CE C toolchain, needs arTIfiCE on OS 5.8.2) | Not started |
| `esp32/` | Dongle firmware for the ESP32-S3 camera board | Not started |
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

## Step 2: test the calculator program with the bridge

Before the dongle is ready, the calculator program can be tested against your computer:

```bash
python bridge.py --serial /dev/cu.usbmodem1101   # Mac (run ls /dev/cu.* to find it)
python bridge.py --serial COM3                   # Windows (check Device Manager)
```

## Protocol

The calculator speaks the same protocol to the dongle and to the bridge. Plain ASCII, one
message per line ending in `\n`, except preview frames, which carry raw pixel bytes.

| Direction | Message | Meaning |
|---|---|---|
| calculator to dongle | `PING` | Check the dongle is there |
| calculator to dongle | `Q:<question>` | Ask a question |
| calculator to dongle | `VIEW` | Send one camera preview frame |
| calculator to dongle | `PHOTO` | Take a full picture and send it to Claude |
| calculator to dongle | `PHOTO:<note>` | Same, with a note such as "just part b" |
| calculator to dongle | `SCAN` | List nearby Wi-Fi networks |
| calculator to dongle | `WIFI:<name>\t<password>` | Join a network and remember it |
| calculator to dongle | `STATUS` | Report Wi-Fi and Claude status |
| dongle to calculator | `PONG` | Reply to `PING` |
| dongle to calculator | `A:<line>` | One screen line of an answer (26 characters max) |
| dongle to calculator | `E:<message>` | An error to show on screen |
| dongle to calculator | `N:<network>` | One network from `SCAN` |
| dongle to calculator | `S:<line>` | One status line from `STATUS` or `WIFI` |
| dongle to calculator | `F:<width>,<height>,<bytes>` | A preview frame; exactly `<bytes>` bytes of 8-bit grayscale pixels follow |
| dongle to calculator | `END` | The reply is complete |

`PHOTO` replies may take 10-30 seconds while Claude reads the picture. The bridge
answers `VIEW`, `PHOTO`, `SCAN` and `WIFI` with an error, since your computer has no
camera hooked up to the calculator.

## Running the tests

```bash
pip install pytest
python -m pytest
```

The tests use a fake Claude client, so they don't need an API key or cost anything.
