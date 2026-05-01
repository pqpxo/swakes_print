import json
from io import BytesIO

from PIL import Image
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send

with open("config.json", "r") as f:
    CONFIG = json.load(f)


def print_pillow_image(img: Image.Image, label_size=None):
    """
    Print a Pillow Image to the Brother QL printer.
    label_size can be passed in from the Flask app (dropdown),
    otherwise we fall back to the default in config.json.
    """

    model = CONFIG["printer"]["model"]
    device = CONFIG["printer"]["device"]
    backend = CONFIG["printer"]["backend"]

    # Use passed-in label size or fallback to config default
    if not label_size:
        label_size = CONFIG["label"]["default_size"]

    qlr = BrotherQLRaster(model)
    qlr.exception_on_warning = True

    instructions = convert(
        qlr=qlr,
        images=[img],
        label=label_size,
        rotate="auto",
        threshold=70,
        dither=False,
        compress=True,
        red=False
    )

    send(
        instructions=instructions,
        printer_identifier=device,
        backend_identifier=backend,
        blocking=True
    )
