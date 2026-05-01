import os
import json
import base64
from io import BytesIO

from flask import Flask, request, render_template, redirect, url_for, jsonify
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests

from printer_backend import print_pillow_image

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["UPLOAD_FOLDER_FONTS"]  = "fonts"
app.config["UPLOAD_FOLDER_IMAGES"] = "uploads"

os.makedirs(app.config["UPLOAD_FOLDER_FONTS"],  exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER_IMAGES"], exist_ok=True)
os.makedirs("templates_data", exist_ok=True)

with open("config.json") as f:
    CONFIG = json.load(f)

LABEL_DIMENSIONS = {
    "62x29":  (696, 271),
    "29x90":  (306, 991),
    "62x100": (696, 1109),
    "12":     (142, 500),
    "29":     (306, 500),
}
ALLOWED_TEMPLATES = {"Address Label", "Food Label"}

# ---------------------------------------------------------------------------
# Helpers — dimensions & fonts
# ---------------------------------------------------------------------------
def get_label_dims(label_size):
    return LABEL_DIMENSIONS.get(
        label_size,
        (CONFIG["label"]["canvas_width"], CONFIG["label"]["canvas_height"])
    )

def list_fonts():
    d = app.config["UPLOAD_FOLDER_FONTS"]
    return [f for f in os.listdir(d) if f.lower().endswith((".ttf", ".otf"))] if os.path.isdir(d) else []

def get_font_path(name):
    c = os.path.join(app.config["UPLOAD_FOLDER_FONTS"], name)
    return c if os.path.exists(c) else name

def load_font(name, size):
    try:
        return ImageFont.truetype(get_font_path(name), size)
    except Exception:
        return ImageFont.load_default()

def measure_text(text, font):
    dummy = Image.new("RGB", (10, 10))
    draw  = ImageDraw.Draw(dummy)
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    except AttributeError:
        return draw.textsize(text, font=font)

# ---------------------------------------------------------------------------
# Helpers — templates
# ---------------------------------------------------------------------------
def load_templates():
    out = []
    for fname in os.listdir("templates_data"):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join("templates_data", fname)) as f:
                t = json.load(f)
                if t.get("name") in ALLOWED_TEMPLATES:
                    out.append(t)
        except Exception:
            pass
    out.sort(key=lambda t: t.get("name", ""))
    return out

def load_template_by_name(name):
    for t in load_templates():
        if t.get("name") == name:
            return t
    return None

# ---------------------------------------------------------------------------
# Helpers — rendering
# ---------------------------------------------------------------------------
def render_text(text, font_name, size, bold=False):
    """Render text to a white-background image.
    Uses textbbox offsets so descenders/ascenders never clip."""
    font = load_font(font_name, size)
    dummy = Image.new("RGB", (1, 1), "white")
    draw  = ImageDraw.Draw(dummy)
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        # bb = (left, top, right, bottom); left/top can be negative
        w        = bb[2] - bb[0]
        h        = bb[3] - bb[1]
        ox_extra = -bb[0]   # shift right when left bearing is negative
        oy_extra = -bb[1]   # shift down when ascender sits above anchor
    except AttributeError:
        w, h = draw.textsize(text, font=font)
        ox_extra, oy_extra = 0, 0

    pad  = max(10, size // 5) + (3 if bold else 0)
    img  = Image.new("RGB", (max(1, w + pad * 2), max(1, h + pad * 2)), "white")
    draw = ImageDraw.Draw(img)
    ox = pad + ox_extra
    oy = pad + oy_extra

    if bold:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((ox + dx, oy + dy), text, fill="black", font=font)
    draw.text((ox, oy), text, fill="black", font=font)
    return img


def render_centered_text(text, font_name, size, lw, lh, bold=False):
    font = load_font(font_name, size)
    img  = Image.new("RGB", (lw, lh), "white")
    draw = ImageDraw.Draw(img)
    tw, th = measure_text(text, font)
    cx, cy = (lw - tw) // 2, (lh - th) // 2
    if bold:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((cx + dx, cy + dy), text, fill="black", font=font)
    draw.text((cx, cy), text, fill="black", font=font)
    return img


def compose_label(elements, lw, lh):
    """Composite all elements onto a white label canvas, respecting alpha.
    Images may be positioned partially or fully outside the canvas — only
    the visible intersection is pasted, so out-of-bounds placement is safe."""
    canvas = Image.new("RGB", (lw, lh), "white")
    for el in elements:
        img = el["image"]
        x, y = int(el["position"][0]), int(el["position"][1])
        iw, ih = img.width, img.height

        # Compute the intersection of the image rect with the canvas rect
        vis_x1 = max(0, x);   vis_y1 = max(0, y)
        vis_x2 = min(lw, x + iw); vis_y2 = min(lh, y + ih)
        if vis_x2 <= vis_x1 or vis_y2 <= vis_y1:
            continue  # fully outside — nothing to draw

        # Crop to the visible portion of the image
        cropped = img.crop((vis_x1 - x, vis_y1 - y, vis_x2 - x, vis_y2 - y))

        if cropped.mode == "RGBA":
            canvas.paste(cropped, (vis_x1, vis_y1), mask=cropped.split()[3])
        elif cropped.mode == "LA":
            rgba = cropped.convert("RGBA")
            canvas.paste(rgba, (vis_x1, vis_y1), mask=rgba.split()[3])
        else:
            canvas.paste(cropped.convert("RGB"), (vis_x1, vis_y1))
    return canvas


def render_template_elements(template, params, position_overrides=None,
                              size_overrides=None, bold_fields=None):
    position_overrides = position_overrides or {}
    size_overrides     = size_overrides or {}
    bold_fields        = bold_fields or set()
    out = []
    for el in template.get("elements", []):
        if el.get("type") != "text":
            continue
        field   = el["field"]
        default = el.get("default", "")
        text    = params.get(field)
        if text is None or text == "":
            text = default
        fname   = el.get("font", CONFIG["label"]["default_font"])
        size    = size_overrides.get(field, int(el.get("size", CONFIG["label"]["default_font_size"])))
        pos     = position_overrides.get(field, el.get("position", [0, 0]))
        bold    = field in bold_fields
        out.append({"type": "text", "image": render_text(text, fname, size, bold), "position": tuple(pos)})
    return out

# ---------------------------------------------------------------------------
# Helpers — QR
# ---------------------------------------------------------------------------
def build_qr_string(params):
    """Return the string to encode, or None if data is insufficient."""
    qr_type = params.get("qr_type", "website")
    if qr_type == "website":
        url = (params.get("qr_url") or "").strip()
        return url or None
    if qr_type == "text":
        txt = (params.get("qr_text_content") or "").strip()
        return txt or None
    if qr_type == "wifi":
        ssid = (params.get("wifi_ssid") or "").strip()
        if not ssid:
            return None
        password = params.get("wifi_password") or ""
        enc      = params.get("wifi_enc") or "WPA"
        hidden   = params.get("wifi_hidden")
        hidden_s = "true" if hidden in (True, "true", "on", "1") else "false"
        return "WIFI:T:%s;S:%s;P:%s;H:%s;;" % (enc, ssid, password, hidden_s)
    if qr_type == "vcard":
        first = (params.get("vcard_first") or "").strip()
        last  = (params.get("vcard_last")  or "").strip()
        full  = (first + " " + last).strip()
        if not full:
            return None
        phone = (params.get("vcard_phone") or "").strip()
        email = (params.get("vcard_email") or "").strip()
        org   = (params.get("vcard_org")   or "").strip()
        url   = (params.get("vcard_url")   or "").strip()
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            "FN:%s" % full,
            "N:%s;%s;;;" % (last, first),
        ]
        if org:   lines.append("ORG:%s" % org)
        if phone: lines.append("TEL:%s" % phone)
        if email: lines.append("EMAIL:%s" % email)
        if url:   lines.append("URL:%s" % url)
        lines.append("END:VCARD")
        return "\n".join(lines)
    return None


def generate_qr_image(data, lw, lh):
    """QR sized to fill the label (centred layout for website/text types)."""
    target   = max(20, min(lw, lh) - 20)
    qr = qrcode.QRCode(border=2)
    qr.add_data(data)
    qr.make(fit=True)
    modules  = qr.modules_count + 4
    box_size = max(1, target // modules)
    qr2 = qrcode.QRCode(box_size=box_size, border=2)
    qr2.add_data(data)
    qr2.make(fit=True)
    return qr2.make_image(fill_color="black", back_color="white").convert("RGB")


def generate_wifi_qr_image(data, lh):
    """QR sized to fill label height (for the WiFi left-side layout)."""
    target   = max(20, lh - 20)
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    modules  = qr.modules_count + 2
    box_size = max(1, target // modules)
    qr2 = qrcode.QRCode(box_size=box_size, border=1)
    qr2.add_data(data)
    qr2.make(fit=True)
    return qr2.make_image(fill_color="black", back_color="white").convert("RGB")


def render_wifi_text_block(font_name, available_w, lh):
    """Legacy: Render 'Scan to / Connect to / WiFi' auto-sized to fit width AND height."""
    lines  = ["Scan to", "Connect to", "WiFi"]
    max_h  = lh - 20
    size   = 80
    while size > 10:
        font     = load_font(font_name, size)
        max_ln_w = max(measure_text(ln, font)[0] for ln in lines)
        lh_vals  = [measure_text(ln, font)[1] for ln in lines]
        spacing  = max(4, size // 8)
        pad      = max(8, size // 5)
        total_h  = sum(lh_vals) + spacing * (len(lh_vals) - 1) + pad
        if max_ln_w <= available_w - 4 and total_h <= max_h:
            break
        size -= 2
    font    = load_font(font_name, size)
    lh_vals = [measure_text(ln, font)[1] for ln in lines]
    spacing = max(4, size // 8)
    total_h = sum(lh_vals) + spacing * (len(lh_vals) - 1) + max(8, size // 5)

    img  = Image.new("RGB", (max(1, available_w), max(1, total_h)), "white")
    draw = ImageDraw.Draw(img)
    y = 0
    for ln, h in zip(lines, lh_vals):
        w_ln = measure_text(ln, font)[0]
        cx   = (available_w - w_ln) // 2
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((cx + dx, y + dy), ln, fill="black", font=font)
        draw.text((cx, y), ln, fill="black", font=font)
        y += h + spacing
    return img, total_h


def render_qr_side_text(text, font_name, available_w, lh, size=None, bold=False):
    """Render arbitrary multi-line text for the right side of a QR layout.
    If size is None, auto-sizes to fit. Renders a tight (text-width) image.
    Returns (image, height).

    Bottom padding is baked in because textbbox measurements can underestimate
    the true rendered extent of the final line (baseline offset vs anchor offset),
    causing the bottom of the last glyph to clip without it.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return None, 0

    def _bottom_pad(sz):
        return max(8, sz // 5)

    if size is None:
        # Auto-size: include bottom_pad in the height budget so the image never
        # overflows the label when the full padded height is used below.
        max_h = lh - 20
        size  = 80
        while size > 10:
            font     = load_font(font_name, size)
            max_ln_w = max(measure_text(ln, font)[0] for ln in lines)
            lh_vals  = [measure_text(ln, font)[1] for ln in lines]
            spacing  = max(4, size // 7)
            total_h  = sum(lh_vals) + spacing * (len(lh_vals) - 1) + _bottom_pad(size)
            if max_ln_w <= available_w - 4 and total_h <= max_h:
                break
            size -= 2

    font    = load_font(font_name, size)
    lh_vals = [measure_text(ln, font)[1] for ln in lines]
    spacing = max(4, size // 7)
    # Add bottom_pad to the image height so the last glyph's descent never clips
    total_h = sum(lh_vals) + spacing * (len(lh_vals) - 1) + _bottom_pad(size)

    # Tight width: fit actual text (not the full available_w)
    max_ln_w = max(measure_text(ln, font)[0] for ln in lines)
    img_w    = min(max_ln_w + max(8, size // 4), available_w)

    img  = Image.new("RGB", (max(1, img_w), max(1, total_h)), "white")
    draw = ImageDraw.Draw(img)
    y = 0
    for ln, h in zip(lines, lh_vals):
        w_ln = measure_text(ln, font)[0]
        cx   = max(0, (img_w - w_ln) // 2)
        if bold:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        draw.text((cx + dx, y + dy), ln, fill="black", font=font)
        draw.text((cx, y), ln, fill="black", font=font)
        y += h + spacing
    return img, total_h


def _qr_elements(qr_str, lw, lh, qr_pos_override=None, label_text=None,
                  label_text_pos=None, label_size=None, label_bold=False):
    """Build QR label elements.
    With label_text: QR on left, text on right (independently positionable).
    Without:         QR centred on label.
    Returns (elements_list, meta_list) where meta_list has one entry per draggable item."""
    meta_list = []

    if label_text:
        qr_img  = generate_wifi_qr_image(qr_str, lh)
        qr_pos  = qr_pos_override or [10, max(0, (lh - qr_img.height) // 2)]
        elems   = [{"image": qr_img, "position": tuple(qr_pos)}]
        meta_list.append({"field": "qr", "label": "QR Code",
                           "x": qr_pos[0], "y": qr_pos[1],
                           "w": qr_img.width, "h": qr_img.height})

        default_text_x = qr_pos[0] + qr_img.width + 12
        avail_w        = lw - default_text_x - 10
        if avail_w > 20:
            txt_img, txt_h = render_qr_side_text(
                label_text, CONFIG["label"]["default_font"],
                avail_w, lh, label_size, label_bold)
            if txt_img:
                if label_text_pos:
                    txt_x, txt_y = int(label_text_pos[0]), int(label_text_pos[1])
                else:
                    txt_x = default_text_x
                    txt_y = max(0, (lh - txt_h) // 2)
                elems.append({"image": txt_img, "position": (txt_x, txt_y)})
                meta_list.append({"field": "qr_text", "label": "QR Text",
                                   "x": txt_x, "y": txt_y,
                                   "w": txt_img.width, "h": txt_img.height})
    else:
        qr_img  = generate_qr_image(qr_str, lw, lh)
        qr_pos  = qr_pos_override or [(lw - qr_img.width) // 2,
                                       (lh - qr_img.height) // 2]
        elems   = [{"image": qr_img, "position": tuple(qr_pos)}]
        meta_list.append({"field": "qr", "label": "QR Code",
                           "x": qr_pos[0], "y": qr_pos[1],
                           "w": qr_img.width, "h": qr_img.height})

    return elems, meta_list


# ---------------------------------------------------------------------------
# Image helpers — preserve alpha for correct PNG compositing
# ---------------------------------------------------------------------------
def load_image_from_upload(fs):
    img = Image.open(fs.stream)
    # Normalise palette mode
    if img.mode == "P":
        img = img.convert("RGBA")
    # Keep RGBA so compose_label can use alpha mask
    if img.mode not in ("RGBA", "RGB", "L", "LA"):
        img = img.convert("RGBA")
    return img

def load_image_from_base64(data):
    return load_image_bytes(BytesIO(base64.b64decode(data)))

def load_image_bytes(buf):
    img = Image.open(buf)
    if img.mode == "P":
        img = img.convert("RGBA")
    return img

def load_image_from_url(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return load_image_bytes(BytesIO(r.content))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    fonts     = list_fonts()
    templates = load_templates()

    if request.method == "POST":
        label_size    = request.form.get("label_size", CONFIG["label"]["default_size"])
        lw, lh        = get_label_dims(label_size)
        template_name = request.form.get("template_name", "").strip()
        elements      = []

        pos_json = request.form.get("element_positions", "")
        try:
            position_overrides = json.loads(pos_json) if pos_json else {}
        except Exception:
            position_overrides = {}

        size_overrides = {}
        bold_fields    = set()
        for key, val in request.form.items():
            if key.startswith("size_"):
                try:
                    size_overrides[key[5:]] = int(val)
                except ValueError:
                    pass
            elif key.startswith("bold_") and val == "1":
                bold_fields.add(key[5:])

        # --- QR template ---
        if template_name == "QR Code":
            qr_str    = build_qr_string(request.form)
            label_txt = (request.form.get("qr_label_text") or "").strip() or None
            label_sz  = size_overrides.get("qr_text") or None
            label_bld = "qr_text" in bold_fields
            if qr_str:
                qr_elems, _ = _qr_elements(
                    qr_str, lw, lh,
                    position_overrides.get("qr"),
                    label_txt,
                    position_overrides.get("qr_text"),
                    label_sz, label_bld)
                elements.extend(qr_elems)

        # --- Named template ---
        elif template_name:
            tmpl = load_template_by_name(template_name)
            if tmpl:
                elements.extend(render_template_elements(
                    tmpl, request.form, position_overrides, size_overrides, bold_fields))

        # --- Free text (up to 5 independent draggable lines, each with own size) ---
        else:
            font      = request.form.get("font", CONFIG["label"]["default_font"])
            dflt_size = int(request.form.get("size", CONFIG["label"]["default_font_size"]))
            all_fields = ["text", "text2", "text3", "text4", "text5"]
            for idx, field in enumerate(all_fields):
                txt  = request.form.get(field, "").strip()
                bold = field in bold_fields
                if not txt:
                    continue
                size = size_overrides.get(field, dflt_size)
                pos  = position_overrides.get(field)
                if pos:
                    elements.append({"image": render_text(txt, font, size, bold),
                                     "position": tuple(pos)})
                else:
                    font_obj = load_font(font, size)
                    tw, th   = measure_text(txt, font_obj)
                    y_frac   = (idx + 0.5) / len(all_fields)
                    elements.append({"image": render_text(txt, font, size, bold),
                                     "position": (max(0, (lw - tw) // 2),
                                                  max(0, int(lh * y_frac) - th // 2))})

        # --- Uploaded images (numbered slots: image_file_0, image_file_1, …) ---
        for i in range(10):
            file = request.files.get(f"image_file_{i}")
            if not file or not file.filename:
                continue
            img = load_image_from_upload(file)
            ix  = int(request.form.get(f"image_x_{i}", 20))
            iy  = int(request.form.get(f"image_y_{i}", 20))
            iw  = max(10, int(request.form.get(f"image_w_{i}", 0)) or img.width)
            ih  = max(10, int(request.form.get(f"image_h_{i}", 0)) or img.height)
            # No position/size clamping — PIL paste clips to canvas bounds automatically,
            # so images can intentionally hang outside or overlap the label edges.
            img = img.resize((iw, ih), Image.LANCZOS)
            elements.append({"image": img, "position": (ix, iy)})

        if not elements:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "message": "Nothing to print"}), 400
            return "Nothing to print", 400

        try:
            print_pillow_image(compose_label(elements, lw, lh))
        except Exception as ex:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "message": str(ex)}), 500
            return f"Print error: {ex}", 500

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "ok"})
        return redirect(url_for("index"))

    return render_template("index.html", fonts=fonts, templates=templates, config=CONFIG, settings=load_settings())


@app.route("/upload_font", methods=["POST"])
def upload_font():
    file = request.files.get("fontfile")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not file or not file.filename:
        if is_ajax:
            return jsonify({"status": "error", "message": "No file received"})
        return redirect(url_for("index"))
    if not file.filename.lower().endswith((".ttf", ".otf")):
        if is_ajax:
            return jsonify({"status": "error", "message": "Only .ttf and .otf files are supported"})
        return "Invalid font type", 400
    font_dir = app.config["UPLOAD_FOLDER_FONTS"]
    os.makedirs(font_dir, exist_ok=True)
    save_path = os.path.join(font_dir, file.filename)
    file.save(save_path)
    if is_ajax:
        return jsonify({"status": "ok", "filename": file.filename})
    return redirect(url_for("index"))


FAVOURITES_FILE = "favourites.json"

def load_favourites():
    if os.path.exists(FAVOURITES_FILE):
        try:
            with open(FAVOURITES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_favourites(favs):
    with open(FAVOURITES_FILE, "w") as f:
        json.dump(favs, f, indent=2)

@app.route("/api/favourites", methods=["GET"])
def get_favourites():
    return jsonify(load_favourites())

@app.route("/api/favourites", methods=["POST"])
def save_favourite():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400
    favs = load_favourites()
    favs[name] = data.get("state", {})
    save_favourites(favs)
    return jsonify({"status": "ok", "name": name})

@app.route("/api/favourites/<name>", methods=["DELETE"])
def delete_favourite(name):
    favs = load_favourites()
    if name in favs:
        del favs[name]
        save_favourites(favs)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "app_name":        "SWAKES Press",
    "app_subtitle":    "Web interface & API for printing labels to your Brother printer",
    "accent_colour":   "#4d8eff",
    "consumables_url": "",
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                s = json.load(f)
            # Merge with defaults so new keys always exist
            return {**DEFAULT_SETTINGS, **s}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def save_settings_file(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(load_settings())

@app.route("/api/settings", methods=["POST"])
def post_settings():
    data = request.get_json() or {}
    s = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in data:
            s[key] = data[key]
    save_settings_file(s)
    return jsonify({"status": "ok", "settings": s})

@app.route("/api/settings/logo", methods=["POST"])
def upload_logo():
    file = request.files.get("logo")
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "No file received"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        return jsonify({"status": "error", "message": "Unsupported image type"}), 400
    logo_path = os.path.join(app.static_folder, "logo.png")
    if ext == ".png":
        file.save(logo_path)
    else:
        img = Image.open(file).convert("RGBA")
        img.save(logo_path, "PNG")
    return jsonify({"status": "ok"})

@app.route("/api/export")
def export_data():
    import zipfile, io as _io
    buf = _io.BytesIO()
    files = {
        "config.json":      "config.json",
        "favourites.json":  FAVOURITES_FILE,
        "settings.json":    SETTINGS_FILE,
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in files.items():
            if os.path.exists(path):
                zf.write(path, arcname)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True, download_name="swakes_press_export.zip")

@app.route("/api/system/restart", methods=["POST"])
def system_restart():
    import subprocess
    try:
        subprocess.Popen(["sudo", "systemctl", "restart", "label_service"])
        return jsonify({"status": "ok", "message": "Restart triggered"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/printer/status")
def printer_status():
    """Check whether the USB printer is physically connected and visible to the OS."""
    try:
        import usb.core
        import re
        device_url = CONFIG.get("printer", {}).get("device", "")
        # Parse vendor + product from usb://0xVVVV:0xPPPP
        m = re.search(r'usb://(0x[\da-fA-F]+):(0x[\da-fA-F]+)', device_url)
        if m:
            vendor_id  = int(m.group(1), 16)
            product_id = int(m.group(2), 16)
        else:
            vendor_id, product_id = 0x04f9, 0x2042  # Brother QL-570 fallback
        dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if dev is not None:
            return jsonify({"online": True,  "message": "Printer Online"})
        return jsonify({"online": False, "message": "Printer Offline"})
    except Exception as e:
        return jsonify({"online": False, "message": "Printer Offline", "error": str(e)})


@app.route("/test_print")
def test_print():
    lw, lh = get_label_dims(CONFIG["label"]["default_size"])
    img    = Image.new("RGB", (lw, lh), "white")
    draw   = ImageDraw.Draw(img)
    font   = load_font(CONFIG["label"]["default_font"], 60)
    text   = "Test Print OK"
    tw, th = measure_text(text, font)
    draw.text(((lw - tw) // 2, (lh - th) // 2), text, fill="black", font=font)
    print_pillow_image(img)
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Live Preview API
# ---------------------------------------------------------------------------
@app.route("/api/preview", methods=["POST"])
def api_preview():
    data       = request.get_json() or {}
    label_size = data.get("label_size", CONFIG["label"]["default_size"])
    lw, lh     = get_label_dims(label_size)
    positions  = data.get("positions", {})
    sizes      = data.get("sizes", {})
    bold_map   = data.get("bold", {})
    bold_set   = {f for f, v in bold_map.items() if v}

    elements     = []
    element_meta = []
    template_name = data.get("template", "")

    # --- QR Code ---
    if template_name == "QR Code":
        qr_str    = build_qr_string(data)
        label_txt = (data.get("qr_label_text") or "").strip() or None
        label_sz  = sizes.get("qr_text") or None
        label_bld = "qr_text" in bold_set
        if qr_str:
            qr_elems, qr_meta_list = _qr_elements(
                qr_str, lw, lh,
                positions.get("qr"),
                label_txt,
                positions.get("qr_text"),
                label_sz, label_bld)
            elements.extend(qr_elems)
            element_meta.extend(qr_meta_list)

    # --- Named template ---
    elif template_name:
        tmpl = load_template_by_name(template_name)
        if tmpl:
            for el in tmpl.get("elements", []):
                if el.get("type") != "text":
                    continue
                field   = el["field"]
                default = el.get("default", "")
                val     = data.get(field)
                text    = val if (val is not None and val != "") else default
                fname   = el.get("font", CONFIG["label"]["default_font"])
                size    = sizes.get(field, int(el.get("size", CONFIG["label"]["default_font_size"])))
                pos     = positions.get(field, el.get("position", [0, 0]))
                bold    = field in bold_set
                img_el  = render_text(text, fname, size, bold)
                elements.append({"image": img_el, "position": tuple(pos)})
                font   = load_font(fname, size)
                tw, th = measure_text(text, font)
                element_meta.append({
                    "field": field, "label": field.replace("_", " ").title(),
                    "x": pos[0], "y": pos[1],
                    "w": max(tw + 24, 80), "h": max(th + 12, 28)
                })

    # --- Free text (supports up to 5 independent draggable lines) ---
    else:
        fname      = data.get("font", CONFIG["label"]["default_font"])
        dflt_size  = int(data.get("size", CONFIG["label"]["default_font_size"]))
        all_fields = [
            ("text",  "Text 1"), ("text2", "Text 2"), ("text3", "Text 3"),
            ("text4", "Text 4"), ("text5", "Text 5"),
        ]
        for idx, (field, label_name) in enumerate(all_fields):
            txt       = data.get(field, "").strip()
            bold      = bool(bold_map.get(field, False))
            field_sz  = sizes.get(field, dflt_size)
            if not txt:
                continue
            pos = positions.get(field)
            if pos is None:
                font_obj = load_font(fname, field_sz)
                tw, th   = measure_text(txt, font_obj)
                y_frac   = (idx + 0.5) / len(all_fields)
                pos      = [max(0, (lw - tw) // 2), max(0, int(lh * y_frac) - th // 2)]
            img_el = render_text(txt, fname, field_sz, bold)
            elements.append({"image": img_el, "position": tuple(pos)})
            font_obj = load_font(fname, field_sz)
            tw, th   = measure_text(txt, font_obj)
            element_meta.append({
                "field": field, "label": label_name,
                "x": pos[0], "y": pos[1],
                "w": max(tw + 24, 80), "h": max(th + 12, 28)
            })

    if not elements and not element_meta:
        return jsonify({"image": None, "elements": [], "label_width": lw, "label_height": lh})

    buf = BytesIO()
    compose_label(elements, lw, lh).save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return jsonify({"image": encoded, "elements": element_meta,
                    "label_width": lw, "label_height": lh})


# ---------------------------------------------------------------------------
# Print API
# ---------------------------------------------------------------------------
@app.route("/api/print", methods=["GET", "POST"])
def api_print():
    label_size = request.values.get("label_size", CONFIG["label"]["default_size"])
    lw, lh     = get_label_dims(label_size)
    elements   = []

    template_name = request.values.get("template", "")
    if template_name == "QR Code":
        qr_str    = build_qr_string(request.values)
        label_txt = (request.values.get("qr_label_text") or "").strip() or None
        if qr_str:
            qr_elems, _ = _qr_elements(qr_str, lw, lh, label_text=label_txt)
            elements.extend(qr_elems)
    elif template_name:
        tmpl = load_template_by_name(template_name)
        if tmpl:
            elements.extend(render_template_elements(tmpl, request.values))

    text = request.values.get("text")
    if text:
        font = request.values.get("font", CONFIG["label"]["default_font"])
        size = int(request.values.get("size", CONFIG["label"]["default_font_size"]))
        elements.append({"image": render_centered_text(text, font, size, lw, lh),
                          "position": (0, 0)})

    if "image_file" in request.files and request.files["image_file"].filename:
        img = load_image_from_upload(request.files["image_file"])
        elements.append({"image": img, "position": (20, 20)})

    if request.is_json:
        d = request.get_json(silent=True) or {}
        if "image_base64" in d:
            img = load_image_from_base64(d["image_base64"])
            elements.append({"image": img, "position": (20, 20)})

    image_url = request.values.get("image_url")
    if image_url:
        img = load_image_from_url(image_url)
        elements.append({"image": img, "position": (20, 20)})

    if not elements:
        return jsonify({"status": "error", "message": "No content"}), 400

    print_pillow_image(compose_label(elements, lw, lh))
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
