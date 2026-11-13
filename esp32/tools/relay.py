"""Connect the calculator to the dongle through a computer, for testing before
you have the OTG cable. Plug both into the computer, start CLAUDE on the
calculator, then run:

    .venv/bin/python esp32/tools/relay.py

Everything the calculator sends goes to the dongle and back, so questions,
photos, Wi-Fi and credit all work as if the dongle were plugged straight in.
Ctrl+C stops it.
"""

import argparse
import glob
import subprocess
import sys
import threading
import time

import serial


def usb_product(port):
    """Name the USB device behind a /dev/cu.usbmodem port (macOS), or ''."""
    try:
        tree = subprocess.run(["ioreg", "-p", "IOUSB", "-l", "-w0"], capture_output=True, text=True).stdout
    except OSError:
        return ""
    serial_no = port.rsplit("usbmodem", 1)[-1][:-1]  # macOS adds one digit
    product = ""
    for line in tree.splitlines():
        if '"USB Product Name"' in line:
            product = line.split("=", 1)[1].strip().strip('"')
        if '"USB Serial Number"' in line and serial_no and serial_no in line:
            return product
    return ""


def find_ports():
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    calc = [p for p in ports if "84 Plus CE" in usb_product(p)]
    dongle = [p for p in ports if p not in calc]
    if not dongle:
        sys.exit("Dongle not found. Plug it into this computer.")
    if not calc:
        sys.exit("Calculator not found. Plug it in and start CLAUDE on it first.")
    return calc[0], dongle[0]


def pump(src, dst, label, show):
    buf = b""
    while True:
        data = src.read(src.in_waiting or 1)
        if not data:
            continue
        dst.write(data)
        dst.flush()
        if show:
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("ascii", "replace")
                if not text.startswith("F:"):  # don't print preview frames
                    print(f"{label} {text[:70]}")
                if len(buf) > 4096:
                    buf = b""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calc")
    ap.add_argument("--dongle")
    ap.add_argument("--quiet", action="store_true", help="don't print the messages")
    args = ap.parse_args()
    calc_port, dongle_port = find_ports() if not (args.calc and args.dongle) else (args.calc, args.dongle)
    calc = serial.Serial(calc_port, 115200, timeout=0.05)
    dongle = serial.Serial(dongle_port, 115200, timeout=0.05)
    print(f"Calculator {calc_port} <-> dongle {dongle_port}. Ctrl+C to stop.")
    for a, b, label in [(calc, dongle, "calc  >"), (dongle, calc, "dongle<")]:
        threading.Thread(target=pump, args=(a, b, label, not args.quiet), daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
