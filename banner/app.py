import base64, io, os, time, re
from flask import Flask, send_file, request, make_response
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from mcstatus import JavaServer

# Config via env (fallbacks)
SERVER_NAME = os.getenv("SERVER_NAME", "My Minecraft Server")
SERVER_URL = os.getenv("SERVER_URL", "127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "25565")

DISPLAY_PORT = os.getenv("DISPLAY_PORT", "True").strip().lower() == "true"
DISPLAY_MOTD = os.getenv("DISPLAY_MOTD", "True").strip().lower() == "true"
DISPLAY_PING = os.getenv("DISPLAY_PING", "True").strip().lower() == "true"
DISPLAY_VERSION = os.getenv("DISPLAY_VERSION", "True").strip().lower() == "true"
DISPLAY_PLAYERS = os.getenv("DISPLAY_PLAYERS", "True").strip().lower() == "true"
DISPLAY_TIMESTAMP = os.getenv("DISPLAY_TIMESTAMP", "True").strip().lower() == "true"

# Render size settings
BANNER_WIDTH  = int(os.getenv("BANNER_WIDTH", "900"))
BANNER_HEIGHT = int(os.getenv("BANNER_HEIGHT", "240"))
BANNER_SCALE  = float(os.getenv("BANNER_SCALE", "1.0"))

def load_font(path, size):
    return ImageFont.truetype(path, size=size) if os.path.exists(path) else ImageFont.load_default()

def scaled(size: int, s: float) -> int:
    # Round and clamp to at least 1px where meaningful
    v = max(1, int(round(size * s)))
    return v

def get_fonts(scale: float):
    # Scale font sizes according to BANNER_SCALE so we rasterize at final resolution
    try:
        return (
            load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", scaled(34, scale)),  # FONT_LG
            load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       scaled(20, scale)),  # FONT_MD
            load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       scaled(16, scale)),  # FONT_SM
            load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       scaled(14, scale)),  # FONT_XS
        )
    except Exception:
        # Fallback to default bitmap fonts (already size-agnostic)
        return (ImageFont.load_default(),)*4

# Strip Minecraft formatting (legacy § codes and RGB sequence)
_MC_LEGACY = re.compile(r"§[0-9A-FK-ORa-fk-or]")
_MC_RGBSEQ = re.compile(r"(?:§x(?:§[0-9A-Fa-f]){6})")
def clean_motd(s: str) -> str:
    if not s:
        return ""
    s = _MC_RGBSEQ.sub("", s)
    s = _MC_LEGACY.sub("", s)
    return s.replace("\n", " ").strip()

def hex_to_rgba(hex_str, alpha=255):
    h = hex_str.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return (r,g,b,alpha)
    return (64, 226, 140, alpha)  # fallback accent

app = Flask(__name__)

def ping_server(address: str):
    try:
        server = JavaServer.lookup(address)
        status = server.status()

        # Prefer new-style PIL image (mcstatus>=11)
        icon_img = None
        if getattr(status, "icon", None) is not None:
            icon_img = status.icon.convert("RGBA")
        elif getattr(status, "icon", None):
            b64 = status.icon.split(",", 1)[1]
            icon_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")

        motd = getattr(status.description, "raw", None) or str(status.description)
        motd = clean_motd(motd)

        return {
            "online": True,
            "motd": motd,
            "players_online": status.players.online,
            "players_max": status.players.max,
            "latency": int(round(status.latency)),
            "version": getattr(status.version, "name", None) or "Unknown",
            "icon": icon_img,
        }
    except Exception:
        return {
            "online": False, "motd": "", "players_online": 0, "players_max": 0,
            "latency": None, "version": "Offline", "icon": None,
        }

BASE_W, BASE_H = 900, 240  # design reference

def draw_banner(data, address, server_name):
    # Final canvas from env
    W, H = int(BANNER_WIDTH), int(BANNER_HEIGHT)

    # Scale so the content fits both dimensions (height included)
    # You can still keep BANNER_SCALE in .env to globally grow/shrink.
    fit_scale = min(W / BASE_W, H / BASE_H)
    S = fit_scale * float(BANNER_SCALE)

    # Fonts at scaled size
    FONT_LG, FONT_MD, FONT_SM, FONT_XS = get_fonts(S)

    # Colors
    BG      = (15, 17, 21, 255)
    PANEL   = (26, 29, 36, 255)
    EDGE    = (54, 58, 66, 255)
    TXT     = (236, 240, 244, 255)
    SUBTXT  = (186, 194, 204, 255)
    MUTED   = (140, 146, 160, 255)
    ACCENT  = hex_to_rgba(os.getenv("ACCENT_HEX", "#40E28C"), 255)
    BAD     = (226, 86, 86, 255)

    # Final banner image
    banner = Image.new("RGBA", (W, H), BG)

    # ---- draw the whole card on a content-sized surface (preserves aspect) ----
    CW, CH = int(round(BASE_W * S)), int(round(BASE_H * S))
    content_img = Image.new("RGBA", (CW, CH), BG)
    draw = ImageDraw.Draw(content_img)

    pad = scaled(16, S)
    card_w, card_h = CW - 2*pad, CH - 2*pad
    card = Image.new("RGBA", (card_w, card_h), PANEL)
    shadow = Image.new("RGBA", (card_w, card_h), (0,0,0,80))
    shadow = shadow.filter(ImageFilter.GaussianBlur(scaled(6, S)))
    content_img.paste(shadow, (pad+scaled(2,S), pad+scaled(3,S)), shadow)
    content_img.paste(card, (pad, pad))

    # Layout inside the card (same as before but using CW/CH and S)
    left_pad  = pad + scaled(20, S)
    top_pad   = pad + scaled(18, S)
    right_pad = pad + scaled(20, S)

    icon_box = (scaled(150, S), scaled(150, S))
    text_x   = left_pad + icon_box[0] + scaled(20, S)
    content_w = max(scaled(300, S), CW - text_x - right_pad)

    # Icon bg
    icon_bg = Image.new("RGBA", icon_box, (38, 41, 49, 255))
    content_img.paste(icon_bg, (left_pad, top_pad))

    # Icon
    icon = data["icon"]
    if icon is None:
        icon_path = os.getenv("ICON_FILE", "/app/assets/icon.png")
        if os.path.exists(icon_path):
            try:
                icon = Image.open(icon_path).convert("RGBA")
            except Exception:
                icon = None

    if icon is not None:
        icon = icon.resize((scaled(128, S), scaled(128, S)), Image.LANCZOS)
        content_img.paste(icon, (left_pad + scaled(11, S), top_pad + scaled(11, S)), icon)
    else:
        d2 = ImageDraw.Draw(content_img)
        d2.rounded_rectangle(
            [left_pad+scaled(11,S), top_pad+scaled(11,S),
             left_pad+scaled(11,S)+scaled(128,S), top_pad+scaled(11,S)+scaled(128,S)],
            scaled(18, S), outline=EDGE, width=scaled(2, S)
        )
        d2.rectangle([left_pad+scaled(48,S), top_pad+scaled(52,S),
                      left_pad+scaled(82,S),  top_pad+scaled(86,S)], fill=EDGE)
        d2.rectangle([left_pad+scaled(95,S), top_pad+scaled(84,S),
                      left_pad+scaled(117,S), top_pad+scaled(106,S)], fill=EDGE)

    # Title + status chip
    y = top_pad - scaled(2, S)
    draw.text((text_x, y), server_name, font=FONT_LG, fill=TXT)
    name_w = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), server_name, font=FONT_LG)[2]

    status_ok = data["online"]
    chip_text = "ONLINE" if status_ok else "OFFLINE"
    chip_col  = ACCENT if status_ok else BAD
    chip_pad_x, chip_pad_y = scaled(8,S), scaled(3,S)
    chip_bbox = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), chip_text, font=FONT_SM)
    c_w = (chip_bbox[2]-chip_bbox[0]) + 2*chip_pad_x
    c_h = (chip_bbox[3]-chip_bbox[1]) + 2*chip_pad_y
    cx  = text_x + min(name_w + scaled(12, S), max(content_w - c_w, 0))
    cy  = y + scaled(6, S)
    draw.rounded_rectangle([cx, cy, cx + c_w, cy + c_h], scaled(9, S), fill=chip_col)
    draw.text((cx + chip_pad_x, cy + chip_pad_y - scaled(1,S)), chip_text, font=FONT_SM, fill=(20,22,25,255))

    # Meta
    y = top_pad + scaled(46, S)
    parts = [address]
    if data["version"] and DISPLAY_VERSION: parts.append(data["version"])
    if data["latency"] is not None and DISPLAY_PING: parts.append(f"{data['latency']} ms")
    draw.text((text_x, y), " • ".join(parts), font=FONT_MD, fill=SUBTXT)

    # Players bar (responsive to content_w)
    if DISPLAY_PLAYERS:
        y += scaled(36, S)
        draw.text((text_x, y), f"Players: {data['players_online']} / {data['players_max']}", font=FONT_MD, fill=TXT)
        pb_x, pb_y, pb_w, pb_h = text_x, y + scaled(28, S), content_w, scaled(14, S)
        draw.rounded_rectangle([pb_x, pb_y, pb_x+pb_w, pb_y+pb_h], scaled(9,S), outline=EDGE, width=scaled(2,S))
        ratio = 0 if data["players_max"] == 0 else min(1.0, data["players_online"]/data["players_max"])
        if ratio > 0:
            fill_w = max(scaled(8,S), int(pb_w * ratio))
            draw.rounded_rectangle([pb_x, pb_y, pb_x+fill_w, pb_y+pb_h], scaled(9,S), fill=ACCENT)

    # MOTD (trim to width)
    if DISPLAY_MOTD:
        y = pb_y + scaled(26, S) if DISPLAY_PLAYERS else y + scaled(26, S)
        motd = data["motd"] or ""
        if motd:
            t = motd
            while True:
                bbox = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), t, font=FONT_SM)
                if (bbox[2]-bbox[0]) <= content_w or len(t) <= 3:
                    break
                t = t[:-2]
            if t != motd:
                t = t.rstrip() + "…"
            draw.text((text_x, y), t, font=FONT_SM, fill=MUTED)

    # Timestamp (bottom-right of content)
    if DISPLAY_TIMESTAMP:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        ts_bbox = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), ts, font=FONT_XS)
        ts_w = ts_bbox[2]-ts_bbox[0]
        draw.text((CW - pad - scaled(6,S) - ts_w, CH - pad - scaled(12,S)), ts, font=FONT_XS, fill=MUTED)

    # ---- center the content on the final banner ----
    off_x = (W - CW) // 2
    off_y = (H - CH) // 2
    banner.paste(content_img, (off_x, off_y), content_img)
    return banner

@app.route("/")
def index():
    return "OK. Use /banner.png or /banner.png?address=host:port&name=Friendly+Name"

@app.route("/favicon.ico")
def favicon():
    return ("", 204)

@app.route("/banner.png")
def banner():
    url = request.args.get("address", SERVER_URL)
    port = request.args.get("port", SERVER_PORT)
    address = url + ":" + port
    name    = request.args.get("name", SERVER_NAME)

    # URL overrides
    accent_hex = request.args.get("accent")  # e.g. accent=40E28C
    icon_force_none = request.args.get("icon", "") == "none"

    if accent_hex:
        os.environ["ACCENT_HEX"] = "#" + accent_hex.lstrip("#")
    if icon_force_none:
        os.environ["ICON_FILE"] = "/__missing__"

    data = ping_server(address)

    # Render directly at the final size; no post-resize step.
    if DISPLAY_PORT is True:
        img = draw_banner(data, address, name)
    else:
        img = draw_banner(data, url, name)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    resp = make_response(send_file(buf, mimetype="image/png"))
    # Anti-cache headers
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
