#!/usr/bin/env python3
"""Non-destructive image optimization script (Phase 5).

Creates WebP variants at 480 / 960 / 1600 px wide from source images.
Originals are NEVER modified.  Output lands in <source_dir>/optimized/.

Usage:
    pip install Pillow  # or: pip install pillow-avif-plugin for AVIF too
    python scripts/optimize_images.py --source path/to/images

If your images are already served from the backend media endpoint
(/api/v1/media/<uuid>) they are stored as raw bytes in the database.
In that case, see the README for how to re-upload WebP variants instead
of running this script directly against files.
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Install Pillow first:  pip install Pillow", file=sys.stderr)
    sys.exit(1)

WIDTHS   = [480, 960, 1600]
QUALITY  = 80
FORMATS  = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


def optimize(source_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    images = [
        p for p in source_dir.rglob("*")
        if p.suffix.lower() in FORMATS and "optimized" not in p.parts
    ]
    if not images:
        print("No images found.")
        return

    for img_path in images:
        with Image.open(img_path) as img:
            # Preserve EXIF orientation
            if hasattr(img, "_getexif") and img._getexif():
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)

            has_alpha = img.mode in ("RGBA", "LA", "PA")
            base = out_dir / img_path.stem

            for w in WIDTHS:
                if img.width < w:
                    continue   # never upscale
                ratio  = w / img.width
                h      = int(img.height * ratio)
                scaled = img.resize((w, h), Image.LANCZOS)

                # WebP with lossless alpha; lossy otherwise
                out_path = base.parent / f"{img_path.stem}_{w}w.webp"
                save_kw  = {"quality": QUALITY, "method": 6}
                if has_alpha:
                    save_kw["lossless"] = False   # still supports alpha in WebP
                scaled.save(out_dir / out_path.name, format="WEBP", **save_kw)
                print(f"  {out_path.name}  ({w}×{h})")

    print(f"\nDone. {len(images)} source images processed → {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".", help="Directory containing source images")
    args = parser.parse_args()

    src = Path(args.source).resolve()
    out = src / "optimized"
    print(f"Source : {src}\nOutput : {out}\n")
    optimize(src, out)
