"""Talk to the dongle from a computer, the way the calculator would.

    .venv/bin/python esp32/tools/test_dongle.py            # ping, status, one question
    .venv/bin/python esp32/tools/test_dongle.py "what is 2+2?"
    .venv/bin/python esp32/tools/test_dongle.py --photo    # also snap and solve a photo

Finds the dongle's USB serial port by itself (pass --port to choose one).
"""

import argparse
import glob
import sys
import time

import serial


def find_port():
    ports = [p for p in glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*")]
    if not ports:
        sys.exit("No dongle found. Is it plugged in with a data cable?")
    return sorted(ports)[-1]


class Dongle:
    def __init__(self, port):
        self.conn = serial.Serial(port, 115200, timeout=0.2)
        time.sleep(0.3)
        self.conn.reset_input_buffer()

    def send(self, line):
        self.conn.write((line + "\n").encode("ascii", "replace"))
        self.conn.flush()

    def read_line(self, timeout):
        end = time.time() + timeout
        buf = b""
        while time.time() < end:
            buf += self.conn.read(1) if not buf.endswith(b"\n") else b""
            if buf.endswith(b"\n"):
                return buf.decode("ascii", "replace").rstrip("\r\n")
        return None

    def request(self, line, timeout=10):
        """Send one message and collect reply lines up to END."""
        self.send(line)
        lines, start = [], time.time()
        while True:
            got = self.read_line(timeout - (time.time() - start))
            if got is None:
                return lines, False
            if got in ("END", "PONG"):
                if got == "PONG":
                    lines.append(got)
                return lines, True
            if got.startswith("F:"):
                w, h, size = (int(v) for v in got[2:].split(","))
                data = self.conn.read(size)
                lines.append(f"[preview frame {w}x{h}, got {len(data)} of {size} bytes]")
                continue
            lines.append(got)


def show(title, lines, ok, seconds):
    print(f"\n--- {title} ({seconds:.1f} s){'' if ok else '  NO REPLY / TIMED OUT'}")
    print("+" + "-" * 26 + "+")
    for line in lines:
        print("|" + line[2:].ljust(26) + "|" if line[1:2] == ":" else "|" + line.ljust(26) + "|")
    print("+" + "-" * 26 + "+")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", default="What is the derivative of x^3 + 2x?")
    ap.add_argument("--port")
    ap.add_argument("--photo", action="store_true")
    args = ap.parse_args()

    port = args.port or find_port()
    print(f"Using {port}")
    d = Dongle(port)
    steps = [("PING", "PING", 5), ("STATUS", "STATUS", 10), ("Q", "Q:" + args.question, 200)]
    if args.photo:
        steps += [("VIEW", "VIEW", 10), ("SNAP", "SNAP", 20), ("PHOTO", "PHOTO", 200)]
    for title, msg, timeout in steps:
        t = time.time()
        lines, ok = d.request(msg, timeout)
        show(title, lines, ok, time.time() - t)


if __name__ == "__main__":
    main()
