"""Connect the calculator to the dongle through a computer, for testing before
you have the OTG cable. Plug both into the computer, start CLAUDE on the
calculator, then run:

    .venv/bin/python esp32/tools/relay.py

Everything the calculator sends goes to the dongle and back, so questions,
photos, Wi-Fi and credit all work as if the dongle were plugged straight in.
It reconnects by itself when you restart CLAUDE or replug either one.
Ctrl+C stops it.
"""

import argparse
import glob
import subprocess
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


def pump(src, dst, label, show, stop):
    buf = b""
    while not stop.is_set():
        try:
            data = src.read(src.in_waiting or 1)
            if not data:
                continue
            dst.write(data)
            dst.flush()
        except (serial.SerialException, OSError):
            stop.set()  # one side was unplugged or the program quit
            return
        if show:
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("ascii", "replace")
                if not text.startswith("F:"):  # don't print preview frames
                    print(f"{label} {text[:70]}", flush=True)
                if len(buf) > 4096:
                    buf = b""


def ports_now():
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    calc = [p for p in ports if "84 Plus CE" in usb_product(p)]
    dongle = [p for p in ports if p not in calc]
    return (calc[0] if calc else None), (dongle[0] if dongle else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="don't print the messages")
    args = ap.parse_args()
    print("Waiting for the calculator (running CLAUDE) and the dongle. Ctrl+C to stop.", flush=True)
    waiting_shown = False
    try:
        while True:
            calc_port, dongle_port = ports_now()
            if not (calc_port and dongle_port):
                if not waiting_shown:
                    missing = "calculator (start CLAUDE)" if not calc_port else "dongle"
                    print(f"Waiting for the {missing}...", flush=True)
                    waiting_shown = True
                time.sleep(1)
                continue
            waiting_shown = False
            try:
                calc = serial.Serial(calc_port, 115200, timeout=0.05)
                dongle = serial.Serial(dongle_port, 115200, timeout=0.05)
            except (serial.SerialException, OSError):
                time.sleep(1)
                continue
            print(f"Connected: calculator {calc_port} <-> dongle {dongle_port}", flush=True)
            stop = threading.Event()
            threads = [threading.Thread(target=pump, args=(a, b, label, not args.quiet, stop), daemon=True)
                       for a, b, label in [(calc, dongle, "calc  >"), (dongle, calc, "dongle<")]]
            for t in threads:
                t.start()
            while not stop.is_set():
                time.sleep(0.5)
            for port in (calc, dongle):
                try:
                    port.close()
                except Exception:
                    pass
            print("Disconnected. Waiting to reconnect...", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
