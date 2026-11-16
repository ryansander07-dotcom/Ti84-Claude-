"""Chat with a calculator from this computer, using the same pair code.

Speaks the dongle's chat format (chat.cpp): messages go through ntfy.sh,
encrypted with AES-256-GCM using a key made from the pair code.

    .venv/bin/python esp32/tools/chat_peer.py "our pair code"            # read along, type to send
    .venv/bin/python esp32/tools/chat_peer.py "our pair code" --send hi  # send one message and quit

Needs: pip install cryptography requests
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import threading
import uuid

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HOST = "https://ntfy.sh"


def derive(code):
    code = code.strip().lower()
    topic = "ti84c" + hashlib.sha256(("ti84-chat topic|" + code).encode()).hexdigest()[:32]
    key = hashlib.sha256(("ti84-chat key|" + code).encode()).digest()
    return topic, key


def seal(key, sender, name, text):
    nonce = os.urandom(12)
    plain = f"1\n{sender}\n{name}\n{text}".encode()
    return base64.b64encode(nonce + AESGCM(key).encrypt(nonce, plain, None)).decode()


def unseal(key, sealed):
    try:
        raw = base64.b64decode(sealed)
        parts = AESGCM(key).decrypt(raw[:12], raw[12:], None).decode().split("\n", 3)
    except Exception:
        return None
    return parts if len(parts) == 4 and parts[0] == "1" else None


def send(topic, key, sender, name, text):
    r = requests.post(f"{HOST}/{topic}", data=seal(key, sender, name, text), timeout=20)
    r.raise_for_status()
    return r.json()


def listen(topic, key, sender, since="all", on_message=print):
    with requests.get(f"{HOST}/{topic}/json", params={"since": since}, stream=True, timeout=(20, 120)) as r:
        for line in r.iter_lines():
            event = json.loads(line or "{}")
            if event.get("event") != "message":
                continue
            msg = unseal(key, event.get("message", ""))
            if msg:
                on_message(event, msg[1] == sender, msg[2], msg[3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("--name", default="Computer")
    ap.add_argument("--send")
    args = ap.parse_args()
    topic, key = derive(args.code)
    sender = "pc" + uuid.uuid4().hex[:10]
    if args.send:
        send(topic, key, sender, args.name, args.send)
        print("sent")
        return

    def show(event, mine, name, text):
        print(f"\r{'You' if mine else name}: {text}\n> ", end="", flush=True)

    threading.Thread(target=listen, args=(topic, key, sender, "all", show), daemon=True).start()
    print("Type a message and press return. Ctrl+C quits.\n> ", end="", flush=True)
    try:
        for line in sys.stdin:
            if line.strip():
                send(topic, key, sender, args.name, line.strip())
            print("> ", end="", flush=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
