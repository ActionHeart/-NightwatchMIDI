"""Convert a source PNG into a multi-size Windows .ico using Qt only.

Usage:
    python tools/make_icon.py [--input assets/icon.png] [--output assets/icon.ico]

The source image is center-cropped to a square and rendered at the usual
Windows icon sizes (16/24/32/48/64/128/256). build_exe.py picks up
assets/icon.ico automatically; the app also loads it as the window icon.
"""
import argparse
import os
import struct
import sys
from pathlib import Path

SIZES = (16, 24, 32, 48, 64, 128, 256)
ROOT = Path(__file__).resolve().parents[1]


def build_ico(entries):
    """Assemble (size, png_bytes) entries into a PNG-based .ico container."""
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory, blobs = b"", b""
    for size, data in entries:
        dimension = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + directory + blobs


def content_rect(image, threshold=245, alpha_floor=12):
    """Bounding box of non-background pixels, estimated on a small preview."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    preview = image.scaledToWidth(min(image.width(), 256),
                                  Qt.TransformationMode.SmoothTransformation)
    preview = preview.convertToFormat(QImage.Format.Format_ARGB32)
    min_x, min_y, max_x, max_y = preview.width(), preview.height(), -1, -1
    for y in range(preview.height()):
        for x in range(preview.width()):
            pixel = preview.pixelColor(x, y)
            lit = pixel.alpha() > alpha_floor and (pixel.red() < threshold
                                                   or pixel.green() < threshold
                                                   or pixel.blue() < threshold)
            if lit:
                min_x, min_y = min(min_x, x), min(min_y, y)
                max_x, max_y = max(max_x, x), max(max_y, y)
    if max_x < 0:
        return None
    scale_x = image.width() / preview.width()
    scale_y = image.height() / preview.height()
    left, top = int(min_x * scale_x), int(min_y * scale_y)
    right, bottom = int((max_x + 1) * scale_x), int((max_y + 1) * scale_y)
    return left, top, max(1, right - left), max(1, bottom - top)


def square_canvas(image, padding=0.06):
    """Crop to the artwork and center it on a transparent square canvas."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter

    rect = content_rect(image)
    content = image if rect is None else image.copy(*rect)
    if content.width() >= image.width() and content.height() >= image.height():
        content = image
    side = int(max(content.width(), content.height()) * (1 + 2 * padding))
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawImage((side - content.width()) // 2, (side - content.height()) // 2, content)
    painter.end()
    return canvas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "assets" / "icon.png")
    parser.add_argument("--output", type=Path, default=ROOT / "src" / "nightwatch_midi" / "assets" / "icon.ico")
    args = parser.parse_args(argv)
    if not args.input.is_file():
        print(f"Icon source not found: {args.input}")
        print("Save your image as assets/icon.png (square works best) and retry.")
        return 1
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, Qt
    from PySide6.QtGui import QGuiApplication, QImage

    app = QGuiApplication.instance() or QGuiApplication([])
    image = QImage(str(args.input))
    if image.isNull():
        print(f"Unsupported or unreadable image: {args.input}")
        return 1
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    square = square_canvas(image)
    entries = []
    for size in SIZES:
        scaled = square.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        if not scaled.save(buffer, "PNG"):
            print(f"Failed to encode size {size}")
            return 1
        entries.append((size, bytes(buffer.data())))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_ico(entries))
    print(f"Wrote {args.output} ({len(entries)} sizes from {args.input})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
