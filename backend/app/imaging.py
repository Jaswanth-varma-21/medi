"""Step 1: validate an uploaded X-ray image (format, size, basic quality). No clinical interpretation here."""
import io

import numpy as np
from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG", "JPEG", "TIFF", "BMP", "WEBP"}
MAX_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 60_000_000


class ImageError(ValueError):
    """The file cannot be used at all (not an image, unsupported format, too large)."""


def _warn(level, code, message):
    return {"level": level, "code": code, "message": message}


def validate_image(data: bytes, view: str = ""):
    """Return (PIL grayscale image, exam info dict, quality dict). Raises ImageError if unusable."""
    if not data:
        raise ImageError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ImageError("That image is larger than 15 MB.")
    if data[:4] == b"DICM" or data[128:132] == b"DICM":
        raise ImageError("DICOM files are not supported yet. Export the image as PNG or JPEG.")
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageError("That file could not be read as an image.")
    if fmt not in ALLOWED_FORMATS:
        raise ImageError(f"Image format {fmt} is not supported. Use PNG, JPEG, TIFF, BMP or WEBP.")

    w, h = img.size
    if min(w, h) < 128:
        raise ImageError("The image is too small to analyse (shorter side under 128 px).")

    rgb = img.convert("RGB")
    gray = img.convert("L")
    a = np.asarray(gray, dtype=np.float32)
    warnings = []

    if min(w, h) < 512:
        warnings.append(_warn("warn", "low_resolution", f"Low resolution ({w}x{h}). Small findings may be missed."))
    ratio = max(w, h) / min(w, h)
    if ratio > 1.6:
        warnings.append(_warn("warn", "odd_aspect", "Unusual shape for a radiograph. The image may be cropped or a screenshot."))

    hsv = np.asarray(rgb.convert("HSV"), dtype=np.float32)
    sat = float(np.mean(hsv[..., 1]) / 255.0)
    notes = []
    if sat > 0.15:
        # A single-hue tint (for example a blue-tinted radiograph) is still a greyscale image underneath.
        mask = (hsv[..., 1] > 50) & (hsv[..., 2] > 40)
        angles = hsv[..., 0][mask] * (2 * np.pi / 255.0)
        concentration = float(np.hypot(np.cos(angles).mean(), np.sin(angles).mean())) if angles.size else 0.0
        if concentration > 0.8:
            notes.append("The image has a single-colour tint. It is analysed as greyscale.")
        else:
            warnings.append(_warn("warn", "colour_image", "The image is in colour. Radiographs are normally greyscale, so this may not be an X-ray."))

    contrast = float(a.std())
    mean = float(a.mean())
    if contrast < 25:
        warnings.append(_warn("warn", "low_contrast", "Very low contrast. Results would be unreliable."))
    if mean < 25 or mean > 230:
        warnings.append(_warn("warn", "exposure", "The image looks extremely dark or bright (possible exposure problem)."))

    # Sharpness: spread of neighbouring-pixel differences, on a downscaled copy so size does not matter.
    small = np.asarray(gray.resize((min(w, 512), min(h, 512))), dtype=np.float32)
    grad = np.abs(np.diff(small, axis=0))[:, :-1] + np.abs(np.diff(small, axis=1))[:-1, :]
    sharp = float(grad.mean())
    if sharp < 1.5:
        warnings.append(_warn("warn", "blurry", "The image looks blurry or very smooth."))

    status = "warnings" if warnings else "ok"
    exam = {
        "format": fmt,
        "width": w,
        "height": h,
        "size_kb": round(len(data) / 1024),
        "view": view.strip() or None,  # never guessed: it is whatever the person entered
    }
    quality = {
        "status": status,
        "warnings": warnings,
        "notes": notes,
        "metrics": {"contrast": round(contrast, 1), "brightness": round(mean, 1), "colourfulness": round(sat, 2), "sharpness": round(sharp, 1)},
    }
    return gray, exam, quality
