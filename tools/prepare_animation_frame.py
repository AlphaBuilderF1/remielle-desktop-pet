"""Prepare a generated RGBA image for the Windows color-key pet window."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def prepare_frame(source: Path, destination: Path, size: int = 420) -> None:
    image = Image.open(source).convert("RGBA")
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    red, green, blue, alpha = image.split()
    binary_alpha = alpha.point(lambda value: 255 if value >= 96 else 0)
    image = Image.merge("RGBA", (red, green, blue, binary_alpha))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=420)
    args = parser.parse_args()
    prepare_frame(args.input, args.output, args.size)


if __name__ == "__main__":
    main()
