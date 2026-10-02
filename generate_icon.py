from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "assets" / "gentill_transcriber.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)

BG = (7, 22, 43, 255)
BLUE = (37, 99, 235, 255)
LIGHT = (96, 165, 250, 255)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(size: int) -> bytes:
    pixels = bytearray(size * size * 4)

    def put(x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < size and 0 <= y < size:
            offset = (y * size + x) * 4
            pixels[offset:offset + 4] = bytes(color)

    def rounded_rect(x0: int, y0: int, x1: int, y1: int, radius: int, color) -> None:
        for y in range(y0, y1):
            for x in range(x0, x1):
                dx = 0
                dy = 0
                if x < x0 + radius:
                    dx = x0 + radius - x
                elif x >= x1 - radius:
                    dx = x - (x1 - radius - 1)
                if y < y0 + radius:
                    dy = y0 + radius - y
                elif y >= y1 - radius:
                    dy = y - (y1 - radius - 1)
                if dx == 0 or dy == 0 or dx * dx + dy * dy <= radius * radius:
                    put(x, y, color)

    def rect(x0: int, y0: int, x1: int, y1: int, color) -> None:
        for y in range(max(0, y0), min(size, y1)):
            for x in range(max(0, x0), min(size, x1)):
                put(x, y, color)

    margin = max(1, round(size * 0.04))
    radius = max(2, round(size * 0.18))
    rounded_rect(margin, margin, size - margin, size - margin, radius, BG)

    center = size // 2
    bar_width = max(1, round(size * 0.055))
    gap = max(1, round(size * 0.028))
    heights = (0.25, 0.48, 0.68, 0.45, 0.25)
    start_x = round(size * 0.16)
    for index, ratio in enumerate(heights):
        height = max(2, round(size * ratio))
        x0 = start_x + index * (bar_width + gap)
        y0 = center - height // 2
        color = LIGHT if index % 2 == 0 else BLUE
        rect(x0, y0, x0 + bar_width, y0 + height, color)

    line = max(1, round(size * 0.035))
    left = round(size * 0.68)
    right = round(size * 0.87)
    top = round(size * 0.23)
    bottom = round(size * 0.77)
    rect(left, top, right, top + line, LIGHT)
    rect(right - line, top, right, bottom, LIGHT)
    rect(left, bottom - line, right, bottom, LIGHT)

    inner_left = left + line
    inner_right = right - line * 2
    for ratio in (0.38, 0.50, 0.62):
        y = round(size * ratio)
        rect(inner_left, y, inner_right, y + max(1, line // 2), BLUE)

    scanlines = bytearray()
    stride = size * 4
    for y in range(size):
        scanlines.append(0)
        start = y * stride
        scanlines.extend(pixels[start:start + stride])

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    images = [(size, _png(size)) for size in SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    payload = bytearray()

    for size, image in images:
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(image),
                offset,
            )
        )
        payload.extend(image)
        offset += len(image)

    OUTPUT.write_bytes(header + bytes(entries) + bytes(payload))
    print(f"ICON_GENERATE=PASS path={OUTPUT} bytes={OUTPUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
