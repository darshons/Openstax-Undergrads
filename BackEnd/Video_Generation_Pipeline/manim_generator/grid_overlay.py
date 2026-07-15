"""Grid-anchor overlay for the visual layout critic.

Ported from the TheoremExplainAgent OpenStax fork (src/core/grid_overlay.py),
which itself ports the spatial-anchoring idea from Code2Video (arXiv
2510.01174): a labeled 6x6 grid is drawn over a rendered scene snapshot so the
VLM can describe layout defects by concrete cell ("title at B2 overlaps
formula at C2") instead of vague spatial language. VLMs are weak at raw
spatial judgement; naming anchor points measurably improves overlap detection.

The grid covers the full 16:9 frame and is used only as a visual reference for
critique — generated code keeps its normal positioning.

Rows are A-F (top to bottom), columns 1-6 (left to right). Cell labels are A1..F6.
"""

from __future__ import annotations

import os
from typing import Tuple, Union

from PIL import Image, ImageDraw, ImageFont

ROWS = ["A", "B", "C", "D", "E", "F"]
COLS = ["1", "2", "3", "4", "5", "6"]

# Manim's default frame in scene units, for translating a grid cell back to a
# position hint if ever needed by downstream code. Full 16:9 frame.
FRAME_X = (-7.111, 7.111)
FRAME_Y = (4.0, -4.0)  # top -> bottom (row A is the top)


def _load_font(size: int):
    """Best-effort system font; falls back to PIL's bitmap font."""
    for name in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def cell_to_scene_xy(cell: str) -> Tuple[float, float]:
    """Map a grid cell label (e.g. 'C4') to the scene-unit center of that cell.

    Useful if a caller wants to turn a critic's cell reference into an actual
    Manim coordinate. Returns (x, y) in Manim scene units.
    """
    cell = cell.strip().upper()
    row, col = cell[0], cell[1:]
    i, j = ROWS.index(row), COLS.index(col)
    cw = (FRAME_X[1] - FRAME_X[0]) / len(COLS)
    ch = (FRAME_Y[1] - FRAME_Y[0]) / len(ROWS)
    x = FRAME_X[0] + (j + 0.5) * cw
    y = FRAME_Y[0] + (i + 0.5) * ch
    return (x, y)


def overlay_grid(
    image: Union[str, Image.Image],
    output_path: str,
    line_rgba: Tuple[int, int, int, int] = (0, 255, 255, 140),
    label_rgba: Tuple[int, int, int, int] = (0, 255, 255, 230),
    return_type: str = "path",
) -> Union[str, Image.Image]:
    """Draw a labeled 6x6 grid over ``image`` and save to ``output_path``.

    Args:
        image: Path to a snapshot PNG or a PIL Image (the clean rendered frame).
        output_path: Where to write the grid-overlaid PNG.
        line_rgba: Grid line colour (semi-transparent cyan by default).
        label_rgba: Cell-label colour.
        return_type: "path" -> return output_path; "image" -> return PIL Image.

    Returns:
        The output path or the PIL Image, per ``return_type``.
    """
    base = Image.open(image) if isinstance(image, str) else image
    base = base.convert("RGBA")
    w, h = base.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    n_rows, n_cols = len(ROWS), len(COLS)
    cw, ch = w / n_cols, h / n_rows
    font = _load_font(max(14, int(min(cw, ch) * 0.18)))

    # vertical + horizontal lines
    for j in range(n_cols + 1):
        x = round(j * cw)
        draw.line([(x, 0), (x, h)], fill=line_rgba, width=2)
    for i in range(n_rows + 1):
        y = round(i * ch)
        draw.line([(0, y), (w, y)], fill=line_rgba, width=2)

    # cell labels in the top-left corner of each cell
    pad = max(3, int(min(cw, ch) * 0.04))
    for i, row in enumerate(ROWS):
        for j, col in enumerate(COLS):
            label = f"{row}{col}"
            draw.text((j * cw + pad, i * ch + pad), label, fill=label_rgba, font=font)

    composited = Image.alpha_composite(base, overlay).convert("RGB")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    composited.save(output_path)

    if return_type == "image":
        return composited
    return output_path
