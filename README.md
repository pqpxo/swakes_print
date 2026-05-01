<p align="center">
  <img src="static/logo.png" alt="SWAKES Print" width="120">
</p>

<h1 align="center">SWAKES Print</h1>
<p align="center">
  A self-hosted web interface and REST API for printing labels on a Brother QL-series printer from a Raspberry Pi.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-2.x-black?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/Raspberry%20Pi-compatible-c51a4a?logo=raspberrypi&logoColor=white" alt="Raspberry Pi">
  <img src="https://img.shields.io/badge/Brother-QL--570-blue" alt="Brother QL-570">
  <img src="https://img.shields.io/badge/licence-MIT-green" alt="MIT Licence">
</p>

---

## Overview

SWAKES Print is a web application that runs on a Raspberry Pi and gives you a browser-based interface to design and print labels directly to a Brother QL-series label printer over USB. It also exposes a REST API so other systems can trigger prints programmatically.

---

## Features

### 🖨️ Label Printing
- Print directly to a **Brother QL-570** (and compatible QL-series) over USB
- Supports multiple label sizes: `62×29mm`, `29×90mm`, `62×100mm`, `12mm`, `29mm`
- Live label preview canvas before printing
- Zoom control on the preview
- Test print to verify connectivity

### 📝 Templates
- **Address Label** — name and up to four address lines, each independently sized and bold
- **Food Label** — name, date made, use-by date, and notes
- **QR Code** — four QR types:
  - 🌐 **Website** — encode any URL
  - 📝 **Text** — encode plain text
  - 📶 **WiFi** — WPA/WPA2, WEP or open networks, with hidden SSID toggle
  - 📇 **vCard** — full contact card (name, organisation, phone, email, website)
- **Free Text** — up to five independent text fields, each with custom font size, bold toggle, and drag-to-reposition

### 🎨 Design Tools
- Per-field **font size** control and **bold** toggle
- Drag elements to reposition on the canvas
- Add and position **images** on the label — drag, resize, and move freely including outside label bounds
- Upload and use **custom fonts** (.ttf / .otf)
- QR label text displayed beside the QR code with custom sizing

### ⭐ Favourites
- Save any label configuration as a named favourite
- Load and restore a saved favourite instantly
- Delete favourites you no longer need
- Stored in `favourites.json` — survives service restarts

### ⚙️ Settings
- **Appearance** — change app name, subtitle, accent colour, and logo via the UI (no code edits needed)
- **Fonts** — upload custom fonts from within the settings panel
- **Consumables** — save a URL to your label supplier for quick access
- **Export** — download a zip of your full configuration (config, favourites, settings)
- **System** — restart the label service from the browser

### 📱 Mobile Friendly
- Responsive layout with **Form / Preview tab switching** on small screens
- Touch-friendly input sizing
- Prevents iOS auto-zoom on input focus

### 🔌 REST API
Trigger prints from any device on the network:

```
GET  /api/print?text=Hello&size=40
POST /api/print                          — multipart/form-data, image_file=<binary>
POST /api/print                          — JSON, {"image_base64": "..."}
GET  /api/print?image_url=https://…/img.png
GET  /api/print?template=Address+Label&name=John&address1=123+Main
GET  /api/print?template=QR+Code&qr_type=wifi&wifi_ssid=Net&wifi_password=pass
```

---

## Requirements

### Hardware
- Raspberry Pi (any model with USB; tested on Raspberry Pi 4)
- Brother QL-570 label printer (QL-500, QL-700, QL-800 also supported with config change)
- USB cable connecting Pi to printer

### Software
- Raspberry Pi OS (Bullseye or later recommended)
- Python 3.9+
- `pip` and `venv`

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/swakes-print.git
cd swakes-print
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install flask pillow qrcode[pil] brother-ql requests pyusb
```

### 4. Configure the printer

Edit `config.json` to match your printer and label:

```json
{
  "printer": {
    "model": "QL-570",
    "device": "usb://0x04f9:0x2042",
    "backend": "pyusb"
  },
  "label": {
    "default_size": "62x29",
    "supported_labels": ["62x29", "29x90", "62x100", "12", "29"],
    "canvas_width": 696,
    "canvas_height": 271,
    "default_font": "DejaVuSans.ttf",
    "default_font_size": 32
  }
}
```

To find your printer's USB vendor/product ID:

```bash
lsusb
# Look for Brother Industries — e.g. ID 04f9:2042
```

### 5. USB permissions

Allow the Pi user to access the USB printer without sudo:

```bash
sudo nano /etc/udev/rules.d/99-brother-ql.rules
```

Add the following line (replace with your vendor/product ID):

```
SUBSYSTEM=="usb", ATTR{idVendor}=="04f9", ATTR{idProduct}=="2042", MODE="0666"
```

Then reload:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 6. Run the application

```bash
python3 app.py
```

Open your browser to `http://<pi-ip-address>:5000`

---

## Running as a systemd Service

To have SWAKES Print start automatically on boot:

### 1. Create the service file

```bash
sudo nano /etc/systemd/system/label_service.service
```

```ini
[Unit]
Description=SWAKES Print Label Service
After=network.target

[Service]
WorkingDirectory=/home/pi/swakes-print
ExecStart=/home/pi/swakes-print/venv/bin/python3 app.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

### 2. Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable label_service
sudo systemctl start label_service
```

### 3. Allow browser-triggered restarts (optional)

To enable the **Restart Service** button in the Settings panel:

```bash
sudo nano /etc/sudoers.d/label_service
```

Add:

```
pi ALL=(ALL) NOPASSWD: /bin/systemctl restart label_service
```

---

## Project Structure

```
swakes-print/
├── app.py                  # Flask application and API routes
├── printer_backend.py      # Brother QL printer interface
├── config.json             # Printer and label configuration
├── favourites.json         # Saved label favourites (auto-created)
├── settings.json           # App settings (auto-created)
├── templates/
│   └── index.html          # Main UI (single-page)
├── static/
│   ├── styles.css          # Dark navy theme
│   └── logo.png            # App logo
├── fonts/                  # Uploaded custom fonts (auto-created)
├── uploads/                # Temporary image uploads (auto-created)
└── templates_data/         # Label template definitions
    ├── address_label.json
    └── food_label.json
```

---

## Configuration Reference

| Key | Description | Default |
|-----|-------------|---------|
| `printer.model` | Brother printer model | `QL-570` |
| `printer.device` | USB device string | `usb://0x04f9:0x2042` |
| `printer.backend` | Print backend | `pyusb` |
| `label.default_size` | Default label size | `62x29` |
| `label.supported_labels` | Available sizes in the UI | `["62x29",...]` |
| `label.default_font` | Font used if none selected | `DejaVuSans.ttf` |
| `label.default_font_size` | Default text size in points | `32` |

---

## Supported Label Sizes

| Size | Pixels (W × H) | Description |
|------|---------------|-------------|
| `62x29` | 696 × 271 | Standard address label |
| `29x90` | 306 × 991 | Tall narrow label |
| `62x100` | 696 × 1109 | Large square label |
| `12` | 142 × 500 | Thin tape |
| `29` | 306 × 500 | Narrow label |

---

## Troubleshooting

**Printer shows Offline**
- Check the USB cable is connected and the printer is powered on
- Verify the USB IDs in `config.json` match `lsusb` output
- Check udev rules are applied: `sudo udevadm trigger`

**Permission denied on USB**
- Run `ls -la /dev/bus/usb/...` and check the device permissions
- Ensure the udev rule is in place and the user is in the correct group

**Font not appearing in dropdown after upload**
- The font upload now lives in **Settings → Fonts**
- After uploading, the font appears immediately in the dropdown without a page refresh

**Restart button does nothing**
- Ensure the sudoers rule is in place (see above)
- Check the service name matches exactly: `label_service`

---

## Licence

MIT — free to use, modify, and distribute. See `LICENSE` for details.

---

<p align="center">Built with ❤️ for the Raspberry Pi community</p>
