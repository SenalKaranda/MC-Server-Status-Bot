#!/usr/bin/env python3
import os, time, signal, sys, requests

WEBHOOK_URL   = os.environ.get("WEBHOOK_URL")                  # required
BANNER_URL    = os.environ.get("BANNER_URL")                   # required
INTERVAL      = int(os.environ.get("INTERVAL", "60"))          # seconds
EMBED_TITLE   = os.environ.get("EMBED_TITLE", "Server Status")
CONTENT       = os.environ.get("CONTENT", "")                  # optional
STATE_FILE    = os.environ.get("STATE_FILE", "/state/message_id.txt")
MESSAGE_ID    = os.environ.get("MESSAGE_ID", "").strip()

if not WEBHOOK_URL or not BANNER_URL:
    print("ERROR: Set WEBHOOK_URL and BANNER_URL env vars.", file=sys.stderr)
    sys.exit(1)

_running = True
def _handle_sigterm(_sig, _frm):
    global _running
    _running = False
signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)

def _img_url():
    return f"{BANNER_URL}{'&' if '?' in BANNER_URL else '?'}v={int(time.time())}"

def _payload(url):
    return {
        "content": CONTENT,
        "embeds": [{"title": EMBED_TITLE, "image": {"url": url}}],
        "allowed_mentions": {"parse": []}
    }

def _read_state():
    try:
        with open(STATE_FILE, "r") as f:
            s = f.read().strip()
            return s if s else None
    except FileNotFoundError:
        return None

def _write_state(mid: str):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(mid)

def _send_new_message() -> str:
    url = _img_url()
    print(f"[post] {url}")
    r = requests.post(WEBHOOK_URL + "?wait=true", json=_payload(url), timeout=15)
    if r.status_code == 429:
        retry = int(r.headers.get("Retry-After", "5"))
        print(f"[429] rate limited, sleeping {retry}s")
        time.sleep(retry)
        return _send_new_message()
    r.raise_for_status()
    return r.json()["id"]

def _edit_message(mid: str) -> str | None:
    url = _img_url()
    edit_url = WEBHOOK_URL + f"/messages/{mid}"
    print(f"[edit] {url}")
    r = requests.patch(edit_url, json=_payload(url), timeout=15)
    if r.status_code == 404:
        print("[warn] message deleted or not found; will recreate.")
        return None
    if r.status_code == 429:
        retry = int(r.headers.get("Retry-After", "5"))
        print(f"[429] rate limited, sleeping {retry}s")
        time.sleep(retry)
        return _edit_message(mid)
    r.raise_for_status()
    return mid

def main():
    mid = MESSAGE_ID or _read_state()
    if not mid:
        try:
            mid = _send_new_message()
            _write_state(mid)
            print(f"[ok] created message id {mid}")
        except Exception as e:
            print(f"[error] failed to create message: {e}", file=sys.stderr)
            sys.exit(2)

    while _running:
        try:
            new_mid = _edit_message(mid)
            if new_mid is None:
                mid = _send_new_message()
                _write_state(mid)
                print(f"[ok] recreated message id {mid}")
            else:
                mid = new_mid
        except Exception as e:
            print(f"[error] edit failed: {e}", file=sys.stderr)
        for _ in range(INTERVAL):
            if not _running:
                break
            time.sleep(1)
    print("[exit] graceful shutdown")

if __name__ == "__main__":
    main()
