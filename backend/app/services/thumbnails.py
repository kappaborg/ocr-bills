"""
Thumbnail generation shared by the serving endpoint and the background
OCR task. Returns JPEG bytes so callers can persist them in Postgres —
the original images live in ephemeral storage on HF Spaces and vanish
on restart; the in-DB thumbnail is what keeps list views visual.
"""
from io import BytesIO
from typing import Optional


def make_thumbnail_bytes(original_path: str, size: int = 200) -> Optional[bytes]:
    """Center-cropped square JPEG (~10-20 KB). None on any failure —
    thumbnails are best-effort and must never break the pipeline."""
    try:
        from PIL import Image, ImageOps

        with Image.open(original_path) as src:
            # Respect phone-camera rotation so the thumbnail isn't sideways.
            src = ImageOps.exif_transpose(src)
            src = src.convert("RGB")
            thumb = ImageOps.fit(src, (size, size), method=Image.Resampling.LANCZOS)
            buf = BytesIO()
            thumb.save(buf, "JPEG", quality=78, optimize=True)
            return buf.getvalue()
    except Exception:
        return None
