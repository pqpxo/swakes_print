#!/usr/bin/env bash
set -e

ROOT="label_service"

echo "Creating project at: $ROOT"

mkdir -p "$ROOT"/{templates,static,templates_data,fonts,uploads}

# ---------------- app.py ----------------
cat > "$ROOT/app.py" << 'EOF'
<APP_PY_CONTENT>
EOF

# ---------------- printer_backend.py ----------------
cat > "$ROOT/printer_backend.py" << 'EOF'
<PRINTER_BACKEND_PY_CONTENT>
EOF

# ---------------- config.json ----------------
cat > "$ROOT/config.json" << 'EOF'
{
  "printer": {
    "model": "QL-570",
    "device": "usb://0x04f9:0x2042",
    "backend": "pyusb"
  },
  "label": {
    "default_size": "62",
    "canvas_width": 800,
    "canvas_height": 300,
    "default_font": "DejaVuSans.ttf",
    "default_font_size": 32
  }
}
EOF

# ---------------- requirements.txt ----------------
cat > "$ROOT/requirements.txt" << 'EOF'
Flask==3.0.2
Pillow==10.3.0
qrcode==7.4.2
requests==2.31.0
brother_ql==0.9.4
EOF

# ---------------- Dockerfile ----------------
cat > "$ROOT/Dockerfile" << 'EOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
EOF

# ---------------- templates/index.html ----------------
cat > "$ROOT/templates/index.html" << 'EOF'
<INDEX_HTML_CONTENT>
EOF

# ---------------- templates/templates_editor.html ----------------
cat > "$ROOT/templates/templates_editor.html" << 'EOF'
<TEMPLATES_EDITOR_HTML_CONTENT>
EOF

# ---------------- templates/templates_editor_simple.html ----------------
cat > "$ROOT/templates/templates_editor_simple.html" << 'EOF'
<TEMPLATES_EDITOR_SIMPLE_HTML_CONTENT>
EOF

# ---------------- static/styles.css ----------------
cat > "$ROOT/static/styles.css" << 'EOF'
body {
  background-color: #f8f9fa;
}

pre {
  white-space: pre-wrap;
}

#preview-img {
  transition: transform 0.1s ease-in-out;
}
EOF

# ---------------- static/editor.css ----------------
cat > "$ROOT/static/editor.css" << 'EOF'
#canvas {
  width: 800px;
  height: 300px;
  border: 2px dashed #aaa;
  position: relative;
  background: white;
  user-select: none;
  background-image:
    linear-gradient(to right, #eee 1px, transparent 1px),
    linear-gradient(to bottom, #eee 1px, transparent 1px);
  background-size: 10px 10px;
}

.element {
  position: absolute;
  border: 1px solid #444;
  background: rgba(0,0,0,0.05);
  padding: 4px;
  cursor: move;
  overflow: hidden;
}

.selected {
  outline: 2px solid #007bff;
}

.resize-handle {
  width: 10px;
  height: 10px;
  background: #007bff;
  position: absolute;
  right: -5px;
  bottom: -5px;
  cursor: se-resize;
}
EOF

# ---------------- static/editor.js ----------------
cat > "$ROOT/static/editor.js" << 'EOF'
<ELEMENT_EDITOR_JS_CONTENT>
EOF

# ---------------- static/editor_simple.js ----------------
cat > "$ROOT/static/editor_simple.js" << 'EOF'
<ELEMENT_EDITOR_SIMPLE_JS_CONTENT>
EOF

# ---------------- templates_data/address_label.json ----------------
cat > "$ROOT/templates_data/address_label.json" << 'EOF'
{
  "name": "Address Label",
  "elements": [
    {
      "type": "text",
      "field": "name",
      "default": "John Doe",
      "font": "DejaVuSans.ttf",
      "size": 36,
      "position": [20, 20],
      "width": 400,
      "height": 50
    },
    {
      "type": "text",
      "field": "address",
      "default": "123 Main Street",
      "font": "DejaVuSans.ttf",
      "size": 28,
      "position": [20, 80],
      "width": 500,
      "height": 40
    },
    {
      "type": "text",
      "field": "city",
      "default": "Nottingham",
      "font": "DejaVuSans.ttf",
      "size": 28,
      "position": [20, 130],
      "width": 500,
      "height": 40
    },
    {
      "type": "qr",
      "field": "qr",
      "position": [600, 20],
      "width": 150,
      "height": 150
    }
  ]
}
EOF

# ---------------- templates_data/food_label.json ----------------
cat > "$ROOT/templates_data/food_label.json" << 'EOF'
{
  "name": "Food Label",
  "elements": [
    {
      "type": "text",
      "field": "item",
      "default": "Chicken Soup",
      "font": "DejaVuSans.ttf",
      "size": 40,
      "position": [20, 20],
      "width": 500,
      "height": 50
    },
    {
      "type": "text",
      "field": "date",
      "default": "2026-04-30",
      "font": "DejaVuSans.ttf",
      "size": 32,
      "position": [20, 90],
      "width": 400,
      "height": 40
    },
    {
      "type": "text",
      "field": "notes",
      "default": "Consume within 48 hours",
      "font": "DejaVuSans.ttf",
      "size": 24,
      "position": [20, 150],
      "width": 500,
      "height": 40
    },
    {
      "type": "qr",
      "field": "qr",
      "position": [600, 20],
      "width": 150,
      "height": 150
    }
  ]
}
EOF

# ---------------- templates_data/sample_image_label.json ----------------
cat > "$ROOT/templates_data/sample_image_label.json" << 'EOF'
{
  "name": "Image Label",
  "elements": [
    {
      "type": "text",
      "field": "title",
      "default": "Sample Product",
      "font": "DejaVuSans.ttf",
      "size": 36,
      "position": [20, 20],
      "width": 400,
      "height": 50
    },
    {
      "type": "image",
      "source": "sample.png",
      "position": [20, 90],
      "width": 200,
      "height": 150
    },
    {
      "type": "qr",
      "field": "qr",
      "position": [600, 20],
      "width": 150,
      "height": 150
    }
  ]
}
EOF

echo "Done. Project created in $ROOT"
echo "Next steps:"
echo "  cd $ROOT"
echo "  python -m venv venv && source venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  python app.py"
