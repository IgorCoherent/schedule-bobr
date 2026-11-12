import io

from PIL import Image, ImageOps

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_OUTPUT_BYTES = 80 * 1024
TARGET_SIZE = (256, 256)


def _detect_format(data: bytes) -> str | None:
    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.format
    except Exception:
        return None


def process_image_to_webp(data: bytes) -> bytes:
    fmt = _detect_format(data)
    if fmt not in ALLOWED_FORMATS:
        raise ValueError("Недопустимый формат изображения")

    with Image.open(io.BytesIO(data)) as opened:
        img: Image.Image = ImageOps.exif_transpose(opened)
        img = img.convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

        quality = 85
        while quality >= 40:
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=quality, method=6)
            out = buf.getvalue()
            if len(out) <= MAX_OUTPUT_BYTES:
                return out
            quality -= 10

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=40, method=6)
        return buf.getvalue()
