from PIL import Image, ImageDraw, ImageFont
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send

# Correct size for 62x29 die-cut
WIDTH, HEIGHT = 696, 271
img = Image.new("RGB", (WIDTH, HEIGHT), "white")
d = ImageDraw.Draw(img)

# Large readable font
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 80)
except:
    font = ImageFont.load_default()

text = "Test Print OK"

# Center the text
tw, th = d.textsize(text, font=font)
x = (WIDTH - tw) // 2
y = (HEIGHT - th) // 2

d.text((x, y), text, fill="black", font=font)

qlr = BrotherQLRaster("QL-570")
qlr.exception_on_warning = True

instructions = convert(
    qlr=qlr,
    images=[img],
    label="62x29",
    rotate="auto",
    threshold=70,
    dither=False,
    compress=True,
    red=False
)

send(
    instructions=instructions,
    printer_identifier="usb://0x04f9:0x2028",
    backend_identifier="pyusb",
    blocking=True
)

print("Sent test print.")
