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
- **Wi-Fi**: shows which network the dongle is on. **Find networks** lists the ones in
  range (saved ones marked `*`); pick one and type its password. **Type a name+password**
  adds a network that doesn't show up (hidden networks). **Saved networks** lists the
  ones it remembers: [enter] joins, [del] forgets. Every network you join is saved
  (up to 10), and the dongle joins the strongest saved one in range by itself whenever
  it isn't connected.
- **Credit**: an estimate of the API credit left. The API doesn't tell an API key its
  balance, so enter the balance from platform.claude.com (Billing) once; the dongle
  subtracts each answer's cost from the tokens it used. The main menu warns when it's
  under $1 (`CREDIT_LOW_USD` in `config.h`) or used up, and so does each answer. After
  adding credit, enter the new balance.
- **Status**: Wi-Fi, signal, camera, model and credit.

One-time setup: put your API key (and, optionally, your home Wi-Fi) in
`esp32/ti84_dongle/secrets.h`, then flash the dongle from your computer over USB-C (see
"Set up the dongle" below). `secrets.h` is in `.gitignore`, so it never gets committed.

**Hardware**

- An ESP32-S3 camera board with native USB and 8 MB PSRAM. Tested: the Meshnology W11
  (16 MB flash, OV3660 camera). The Seeed XIAO ESP32S3 Sense works too. Attach the
  board's antenna; without it Wi-Fi finds no networks.
- A USB OTG cable, mini-USB (male) to USB-C (male). It must be OTG so the calculator
  acts as the USB host and powers the dongle.
- An EEMB 402535 LiPo (3.7 V, 320 mAh) on the board's battery pads, so Wi-Fi never
  browns out the calculator's USB port. The calculator recharges it.
- A 3D-printed case; see [case/README.md](case/README.md) for the three versions.

## What's here

| Folder | What it is | Status |
|---|---|---|
| `bridge/` | Python program that stands in for the dongle on your computer, for testing | Ready to test |
| `calculator/` | `CLAUDE` program for the calculator (CE C toolchain) | Compiles; not yet run on a calculator |
| `esp32/ti84_dongle/` | Dongle firmware (Arduino) for the Meshnology W11 or XIAO ESP32S3 Sense | Tested on the W11: questions, photos, Wi-Fi, credit |
| `case/` | 3D-printable cases: an always-on battery door, a clip-on door with a magnetic pod, and a mini box without a camera | Door sizes need measuring |
| `tests/` | Bridge tests, plus a check that the dongle's C++ text cleanup matches the Python one | |

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

## Step 2: put the program on the calculator

Your OS 5.8.2 blocks C programs by default, so this needs the arTIfiCE jailbreak (works
up to OS 5.8.4; don't update the OS).

1. Install the [CE C toolchain](https://ce-programming.github.io/toolchain/), then build:

   ```bash
   cd calculator
   make
   ```

   This makes `calculator/bin/CLAUDE.8xp`.
2. Get the two other files:
   - `clibs.8xg`, the CE C libraries (graphx, usbdrvce, srldrvce), from
     [CE-Programming/libraries](https://github.com/CE-Programming/libraries/releases).
   - arTIfiCE from [YvanTT/arTIfiCE](https://github.com/YvanTT/arTIfiCE/releases):
     **`arTIfiCE_v2.1.8xp` for OS 5.8.4 and earlier** (including 5.8.2). v3 is only for
     OS 5.8.5 and installs differently.
3. With TI Connect CE, send `arTIfiCE_v2.1.8xp`, `clibs.8xg` and `CLAUDE.8xp` to the
   calculator. On an Apple Silicon Mac, TI Connect CE needs Rosetta
   (`softwareupdate --install-rosetta`).
   TI Connect CE puts everything in the archive. arTIfiCE (the program **A**) has to be
   in RAM: on the calculator press **[2nd] [+]** (MEM), **2: Mem Management/Delete**,
   **Prgm**, move to **A** (it has a `*`, meaning archived) and press **[enter]** so the
   `*` goes away. CLAUDE and the libraries can stay archived.
4. On the calculator: press **[prgm]**, choose **TI-Basic** if it asks, pick the first
   program, **A** (that's arTIfiCE), and press **[enter]** twice. In the arTIfiCE menu
   that opens, pick **CLAUDE** and press **[enter]**. Press **[mode]** to leave the
   arTIfiCE menu. Run **A** again whenever you want to start CLAUDE.

You can try the calculator program before the dongle is built: plug the calculator into
your computer with a normal USB cable, start `CLAUDE`, and run the bridge:

```bash
python bridge.py --serial /dev/cu.usbmodem1101   # Mac (run ls /dev/cu.* to find it)
python bridge.py --serial COM3                   # Windows (check Device Manager)
```

Asking questions and Status work with the bridge. Photo and Wi-Fi need the dongle.

No OTG cable yet? Plug both the calculator (running CLAUDE) and the dongle into the
computer and run `.venv/bin/python esp32/tools/relay.py`. It passes everything between
them, so photos, Wi-Fi and credit work too.

## Step 3: set up the dongle

1. Install the [Arduino IDE](https://www.arduino.cc/en/software) (or `arduino-cli`),
   add the "esp32 by Espressif Systems" boards (version 3.x), and install the
   **ArduinoJson** library (version 7).
2. Copy `esp32/ti84_dongle/secrets.example.h` to `secrets.h` in the same folder. Paste
   your API key in. Your home Wi-Fi is optional; you can add networks from the
   calculator later.
3. Open `esp32/ti84_dongle/ti84_dongle.ino` and pick these settings in the Tools menu:

   | Setting | Meshnology W11 | Seeed XIAO ESP32S3 Sense |
   |---|---|---|
   | Board | ESP32S3 Dev Module | XIAO_ESP32S3 |
   | USB Mode | USB-OTG (TinyUSB) | USB-OTG (TinyUSB) |
   | USB CDC On Boot | Disabled | Disabled |
   | PSRAM | OPI PSRAM | OPI PSRAM |
   | Flash Size | 16MB | (fixed) |
   | Partition Scheme | 16M Flash (3MB APP/9.9MB FATFS) | Default |

   With `arduino-cli`, the board names are
   `esp32:esp32:esp32s3:USBMode=default,CDCOnBoot=default,PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB`
   (W11) and `esp32:esp32:XIAO_ESP32S3:USBMode=default,CDCOnBoot=cdc,PSRAM=opi` (XIAO).
   On an Apple
   Silicon Mac, a "bad CPU type" error during the build means Arduino's sketch scanner
   needs Rosetta: run `softwareupdate --install-rosetta` once.

4. Plug the dongle into your computer and click Upload. If the upload can't find the
   board, hold the tiny **B** (boot) button while plugging it in, then upload again.

To check it before using the calculator, run `.venv/bin/python esp32/tools/test_dongle.py`.
It talks to the dongle over USB the way the calculator does: ping, status, and one
question to Claude. If the camera's wiring is unknown (as on the W11), upload
`esp32/tools/camera_probe/` once; it reports which wiring the camera answers on.

After that, unplug it from the computer and plug it into the calculator with the OTG
cable. Start `CLAUDE`, open **Wi-Fi** to join a network, and you're set. The dongle
remembers up to 5 networks and joins the strongest one in range.

**Using it from the calculator**

- Typing: **[alpha]** switches between numbers/math, lowercase and uppercase. Letters are
  where the calculator prints them in green (A is [math], B is [apps], and so on), [0] is a
  space. **[2nd]** gives extra symbols: sqrt( on [x²], pi on [^], < on [math], > on
  [apps]. **[del]** deletes, **[clear]** clears the line or goes back.
- Photo: the screen shows what the camera sees. Press **[enter]** to take the picture,
  then **[enter]** again to have Claude solve it, or **[y=]** to add a note first
  ("just part b"). **[clear]** retakes.
- Answers scroll with the arrow keys. **[clear]** goes back.
- If the preview is upside down or mirrored, set `CAMERA_VFLIP` or `CAMERA_HMIRROR` in
  `esp32/ti84_dongle/config.h` and upload again.

## Protocol

The calculator speaks the same protocol to the dongle and to the bridge. Plain ASCII, one
message per line ending in `\n`, except preview frames, which carry raw pixel bytes.

| Direction | Message | Meaning |
|---|---|---|
| calculator to dongle | `PING` | Check the dongle is there |
| calculator to dongle | `Q:<question>` | Ask a question |
| calculator to dongle | `VIEW` | Send one camera preview frame |
| calculator to dongle | `SNAP` | Take a full-size picture and keep it |
| calculator to dongle | `PHOTO` | Send the kept picture to Claude (takes one first if there isn't one) |
| calculator to dongle | `PHOTO:<note>` | Same, with a note such as "just part b" |
| calculator to dongle | `SCAN` | List nearby Wi-Fi networks |
| calculator to dongle | `WIFI:<name>\t<password>` | Join a network and remember it |
| calculator to dongle | `SAVED` | List remembered networks |
| calculator to dongle | `JOIN:<name>` | Join a remembered network with its saved password |
| calculator to dongle | `FORGET:<name>` | Forget a remembered network |
| calculator to dongle | `CREDIT` | Report the credit estimate |
| calculator to dongle | `CREDIT:<dollars>` | Set the current balance, such as `CREDIT:4.95` |
| calculator to dongle | `STATUS` | Report Wi-Fi and Claude status |
| dongle to calculator | `PONG` | Reply to `PING` |
| dongle to calculator | `A:<line>` | One screen line of an answer (26 characters max) |
| dongle to calculator | `E:<message>` | An error to show on screen |
| dongle to calculator | `N:<network>` | One network from `SCAN` |
| dongle to calculator | `S:<line>` | One status line from `STATUS`, `SNAP`, `WIFI`, `CREDIT` and others |
| dongle to calculator | `C:<network>` | From `SAVED`: the network it's on now (blank if none) |
| dongle to calculator | `W:<network>` | From `SAVED`: one remembered network |
| dongle to calculator | `K:<cents>,<state>` | Credit estimate, sent with `CREDIT` and after every answer. Cents is -1 if no balance is set; state 0 ok, 1 low, 2 used up, 3 not set |
| dongle to calculator | `F:<width>,<height>,<bytes>` | A preview frame; exactly `<bytes>` bytes of 8-bit grayscale pixels follow, then `END` |
| dongle to calculator | `END` | The reply is complete |

`PHOTO` replies may take 10-60 seconds while Claude reads the picture. The bridge
answers `VIEW`, `SNAP`, `PHOTO`, `SCAN`, `WIFI`, `SAVED`, `JOIN`, `FORGET` and `CREDIT` with an error, since your computer
has no camera hooked up to the calculator.

## Running the tests

```bash
pip install pytest
python -m pytest
```

The tests use a fake Claude client, so they don't need an API key or cost anything.
The text-cleanup comparison also needs a C++ compiler (it skips itself without one).
