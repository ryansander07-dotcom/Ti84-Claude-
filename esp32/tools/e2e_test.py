"""End-to-end test of the dongle, acting exactly like the calculator program does:
the same messages in the same order, with the calculator's time limits. Plug the
dongle into this computer (not through the relay) and run:

    .venv/bin/python esp32/tools/e2e_test.py

It asks Claude two short questions and sends one photo (about 2 cents in all).
It doesn't change your saved Wi-Fi networks or your credit balance.
"""

import glob
import sys
import time

import serial

SCREEN_COLS = 26
PING_TIMEOUT = 3      # calculator: ping() limit
QUICK_TIMEOUT = 10    # calculator: quick requests
IDLE_LIMIT = 30       # calculator: gives up after this long with nothing from the dongle
PREVIEW_BYTES = 160 * 120

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return ok


class Calc:
    """The calculator's side of the link."""

    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=0.05)
        time.sleep(0.3)
        self.s.reset_input_buffer()
        self.buf = b""

    def send(self, line):
        self.s.write(line.encode("ascii") + b"\n")
        self.s.flush()

    def cancel(self):
        self.s.write(b"\x18\n")
        self.s.flush()

    def read_line(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                return line.decode("ascii", "replace").rstrip("\r")
            self.buf += self.s.read(self.s.in_waiting or 1)
        return None

    def read_bytes(self, n, timeout):
        end = time.time() + timeout
        while len(self.buf) < n and time.time() < end:
            self.buf += self.s.read(max(1, min(n - len(self.buf), 4096)))
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def ping(self):
        """calculator ping(): send PING, throw away anything else until PONG."""
        self.send("PING")
        end = time.time() + PING_TIMEOUT
        while time.time() < end:
            line = self.read_line(end - time.time())
            if line == "PONG":
                return True
        return False

    def request(self, msg, idle_limit=QUICK_TIMEOUT):
        """calculator request(): collect lines until END; give up after idle_limit
        seconds with nothing at all from the dongle. Returns (lines, info)."""
        start = time.time()
        if not self.ping():
            return None, {"error": "no PONG"}
        self.send(msg)
        lines, info = [], {"heartbeats": 0, "total": None, "credit": None, "max_gap": 0.0}
        last = time.time()
        while True:
            line = self.read_line(idle_limit - (time.time() - last))
            if line is None:
                info["error"] = f"nothing for {idle_limit} s"
                break
            now = time.time()
            info["max_gap"] = max(info["max_gap"], now - last)
            last = now
            if line == "END":
                break
            if line.startswith("H:"):
                info["heartbeats"] += 1
            elif line.startswith("P:"):
                info["total"] = int(line[2:])
            elif line.startswith("K:"):
                info["credit"] = line[2:]
            else:
                lines.append(line)
        info["seconds"] = time.time() - start
        return lines, info


def find_dongle():
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import relay
    calc, dongle = relay.ports_now()
    if not dongle:
        sys.exit("Dongle not found. Plug it into this computer (stop the relay first).")
    return dongle


def lines_fit(lines):
    bad = [l for l in lines if len(l) > 2 + SCREEN_COLS and l[1:2] == ":" and l[0] in "AES"]
    return not bad, bad[:2]


def page_through(c, first_lines, total):
    """Scroll like show_lines() does: fetch PAGE:n until every line has been seen."""
    got = list(first_lines)
    while len(got) < total:
        lines, info = c.request(f"PAGE:{len(got)}")
        if not lines:
            return got, False
        got += lines
    return got, len(got) == total


def main():
    c = Calc(find_dongle())

    # 1. The link itself
    t = time.time()
    check("PING answers", c.ping(), f"{(time.time() - t) * 1000:.0f} ms")

    # 2. Status and credit (main menu's background check)
    lines, info = c.request("STATUS")
    wifi = next((l for l in (lines or []) if l.startswith("S:Wi-Fi:")), "")
    check("STATUS replies", bool(lines), f"{info.get('seconds', 0):.2f} s")
    check("Wi-Fi connected", "not connected" not in wifi and bool(wifi), wifi[2:])
    check("Camera ready", any(l == "S:Camera: ready" for l in lines or []))
    lines, info = c.request("CREDIT")
    check("CREDIT sends a K: code", info.get("credit") is not None, info.get("credit"))

    # 3. A question, read the way show_lines() reads it
    lines, info = c.request("Q:List the first 20 prime numbers, one per line, then ANSWER: done.", IDLE_LIMIT)
    check("Question answered", any(l.startswith("A:") for l in lines or []) and "error" not in info,
          f"{info.get('seconds', 0):.1f} s, {info.get('heartbeats')} heartbeats, longest silence {info.get('max_gap', 0):.1f} s")
    check("Silence never near the 30 s limit", info.get("max_gap", 99) < 5, f"{info.get('max_gap', 0):.1f} s")
    check("Answer is paged", info.get("total") is not None and len(lines) <= 9,
          f"{info.get('total')} lines, first screen {len(lines)}")
    if info.get("total"):
        all_lines, ok = page_through(c, lines, info["total"])
        check("Scrolling fetches every line", ok, f"{len(all_lines)} of {info['total']}")
        fit, bad = lines_fit(all_lines)
        check("Every line fits 26 columns", fit, str(bad))

    # 4. Cancel: [clear] while Claude is working. The calculator leaves at once;
    #    what matters is that the dongle is ready for the next request quickly.
    for delay in (0.2, 2.0):
        c.send("Q:Write a long story about a calculator, at least 400 words.")
        time.sleep(delay)
        t = time.time()
        c.cancel()
        ok = c.ping()  # the next request's ping
        check(f"Ready again after cancel at {delay} s", ok and time.time() - t < PING_TIMEOUT,
              f"PONG after {time.time() - t:.2f} s")

    # 5. Camera preview, as the photo screen asks for it
    times = []
    for _ in range(5):
        t = time.time()
        c.send("VIEW")
        header = c.read_line(QUICK_TIMEOUT)
        ok = header == f"F:160,120,{PREVIEW_BYTES}"
        data = c.read_bytes(PREVIEW_BYTES, QUICK_TIMEOUT) if ok else b""
        end = c.read_line(QUICK_TIMEOUT) if ok else None
        times.append(time.time() - t)
        if not (ok and len(data) == PREVIEW_BYTES and end == "END"):
            check("Preview frame", False, f"header {header!r}, {len(data)} bytes, end {end!r}")
            break
    else:
        check("Preview frames arrive whole", True, f"{1 / (sum(times) / len(times)):.1f} frames/s over USB")

    # Cancel in the middle of a frame, then the next request must still work
    c.send("VIEW")
    c.read_line(QUICK_TIMEOUT)
    c.read_bytes(4000, QUICK_TIMEOUT)  # [clear] after a few rows
    check("Works after leaving mid-frame", c.ping())

    # 6. Photo: SNAP, then PHOTO with a note
    c.send("SNAP")
    snap = []
    while True:
        l = c.read_line(20)
        if l in (None, "END"):
            break
        snap.append(l)
    check("SNAP takes a picture", "S:Got it." in snap, str(snap))
    lines, info = c.request("PHOTO:In one short sentence, what is in this photo?", IDLE_LIMIT)
    check("Photo answered", any(l.startswith("A:") for l in lines or []) and "error" not in info,
          f"{info.get('seconds', 0):.1f} s, longest silence {info.get('max_gap', 0):.1f} s: "
          + " ".join(l[2:] for l in (lines or [])[:3]))

    # 7. Wi-Fi menu
    lines, info = c.request("SAVED")
    saved = [l[2:] for l in lines or [] if l.startswith("W:")]
    current = next((l[2:] for l in lines or [] if l.startswith("C:")), "")
    check("SAVED lists networks", bool(saved), f"on {current!r}, saved {saved}")
    lines, info = c.request("SCAN", 40)
    nets = [l[2:] for l in lines or [] if l.startswith("N:")]
    check("SCAN finds networks", bool(nets), f"{len(nets)} found in {info.get('seconds', 0):.1f} s")
    if current:
        lines, info = c.request(f"JOIN:{current}", 40)
        check("JOIN a saved network", any("Connected" in l for l in lines or []),
              f"{info.get('seconds', 0):.1f} s")

    # 8. Mistakes the calculator can send
    lines, _ = c.request("Q:   ")
    check("Empty question is refused", any(l.startswith("E:") for l in lines or []))
    lines, _ = c.request("CREDIT:abc")
    check("Bad balance is refused", any(l.startswith("E:") for l in lines or []))
    lines, _ = c.request("PAGE:999")
    check("Page past the end is empty", lines == [])
    lines, _ = c.request("FORGET:no-such-network")
    check("Forgetting an unknown network is refused", any(l.startswith("E:") for l in lines or []))
    lines, _ = c.request("NONSENSE")
    check("Unknown message is refused", any(l.startswith("E:") for l in lines or []))

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} of {len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
