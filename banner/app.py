import base64, io, os, time, re
from flask import Flask, send_file, request, make_response
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from mcstatus import JavaServer

# Config via env (fallbacks)
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS", "127.0.0.1:25565")
SERVER_NAME    = os.getenv("SERVER_NAME", "My Minecraft Server")

def load_font(path, size):
    return ImageFont.truetype(path, size=size) if os.path.exists(path) else ImageFont.load_default()

# Fonts
FONT_LG  = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
FONT_MD  = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
FONT_SM  = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
FONT_XS  = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)

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

def draw_banner(data, address, server_name):
    # Theming
    BG      = (15, 17, 21, 255)
    PANEL   = (26, 29, 36, 255)
    EDGE    = (54, 58, 66, 255)
    TXT     = (236, 240, 244, 255)
    SUBTXT  = (186, 194, 204, 255)
    MUTED   = (140, 146, 160, 255)
    ACCENT  = hex_to_rgba(os.getenv("ACCENT_HEX", "#40E28C"), 255)
    BAD     = (226, 86, 86, 255)

    # Canvas
    W, H = 900, 240
    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Card + soft shadow
    pad = 16
    card = Image.new("RGBA", (W - 2*pad, H - 2*pad), PANEL)
    shadow = Image.new("RGBA", card.size, (0,0,0,80))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img.paste(shadow, (pad+2, pad+3), shadow)
    img.paste(card, (pad, pad))

    # Layout
    left = pad + 20
    top  = pad + 18
    icon_box = (150, 150)
    text_x = left + icon_box[0] + 20

    # Icon area background
    icon_bg = Image.new("RGBA", icon_box, (38, 41, 49, 255))
    img.paste(icon_bg, (left, top))

    # Icon: server -> custom file -> placeholder
    icon = data["icon"]
    if icon is None:
        icon_path = os.getenv("ICON_FILE", "/app/assets/icon.png")
        if os.path.exists(icon_path):
            try:
                icon = Image.open(icon_path).convert("RGBA")
            except Exception:
                icon = None

    if icon is not None:
        icon = icon.resize((128, 128), Image.BICUBIC)
        img.paste(icon, (left + 11, top + 11), icon)
    else:
        d2 = ImageDraw.Draw(img)
        d2.rounded_rectangle([left+11, top+11, left+11+128, top+11+128], 18, outline=EDGE, width=2)
        d2.rectangle([left+48, top+52, left+82, top+86], fill=EDGE)
        d2.rectangle([left+95, top+84, left+117, top+106], fill=EDGE)

    # Title
    y = top - 2
    draw.text((text_x, y), server_name, font=FONT_LG, fill=TXT)
    name_w = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), server_name, font=FONT_LG)[2]

    # Status chip
    status_ok = data["online"]
    chip_text = "ONLINE" if status_ok else "OFFLINE"
    chip_col  = ACCENT if status_ok else BAD
    chip_pad_x, chip_pad_y = 8, 3
    chip_bbox = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), chip_text, font=FONT_SM)
    c_w = (chip_bbox[2]-chip_bbox[0]) + 2*chip_pad_x
    c_h = (chip_bbox[3]-chip_bbox[1]) + 2*chip_pad_y
    cx  = text_x + name_w + 12
    cy  = y + 6
    draw.rounded_rectangle([cx, cy, cx + c_w, cy + c_h], 9, fill=chip_col)
    draw.text((cx + chip_pad_x, cy + chip_pad_y - 1), chip_text, font=FONT_SM, fill=(20,22,25,255))

    # Meta line
    y = top + 46
    meta_parts = [address]
    if data["version"]: meta_parts.append(data["version"])
    if data["latency"] is not None: meta_parts.append(f"{data['latency']} ms")
    draw.text((text_x, y), " • ".join(meta_parts), font=FONT_MD, fill=SUBTXT)

    # Players + bar
    y += 36
    draw.text((text_x, y), f"Players: {data['players_online']} / {data['players_max']}", font=FONT_MD, fill=TXT)
    pb_x, pb_y, pb_w, pb_h = text_x, y + 28, 610, 14
    draw.rounded_rectangle([pb_x, pb_y, pb_x+pb_w, pb_y+pb_h], 9, outline=EDGE, width=2)
    ratio = 0 if data["players_max"] == 0 else min(1.0, data["players_online"]/data["players_max"])
    if ratio > 0:
        fill_w = max(8, int(pb_w * ratio))
        draw.rounded_rectangle([pb_x, pb_y, pb_x+fill_w, pb_y+pb_h], 9, fill=ACCENT)

    # MOTD
    y = pb_y + 26
    motd = data["motd"]
    if len(motd) > 70: motd = motd[:70] + "…"
    if motd:
        draw.text((text_x, y), motd, font=FONT_SM, fill=MUTED)

    # Timestamp (bottom-right)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    ts_bbox = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), ts, font=FONT_XS)
    ts_w = ts_bbox[2]-ts_bbox[0]
    draw.text((W - ts_w - 22, H - 28), ts, font=FONT_XS, fill=MUTED)

    return img

@app.route("/")
def index():
    return "OK. Use /banner.png or /banner.png?address=host:port&name=Friendly+Name"

@app.route("/favicon.ico")
def favicon():
    return ("", 204)

@app.route("/banner.png")
def banner():
    address = request.args.get("address", SERVER_ADDRESS)
    name    = request.args.get("name", SERVER_NAME)

    # URL overrides
    accent_hex = request.args.get("accent")  # e.g. accent=40E28C
    scale = float(request.args.get("scale", "1.0"))
    icon_force_none = request.args.get("icon", "") == "none"

    if accent_hex:
        os.environ["ACCENT_HEX"] = "#" + accent_hex.lstrip("#")
    if icon_force_none:
        os.environ["ICON_FILE"] = "/__missing__"

    data = ping_server(address)
    img = draw_banner(data, address, name)

    if scale != 1.0:
        new_size = (int(img.width*scale), int(img.height*scale))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    resp = make_response(send_file(buf, mimetype="image/png"))
    # Anti-cache headers (Discord ignores; refresher handles cache-busting)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
