"""Copy/paste clipboard for the map editor.

Stores a rectangular region of tile data from one or more layers,
along with the corresponding tile properties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

class PasteMode(Enum):
    ALL_LAYERS = auto(),
    LAYER_1 = auto(),
    LAYER_2 = auto(),
    LAYER_3 = auto(),
    PROPS_ONLY = auto(),

@dataclass
class ClipboardRegion:
    """A rectangular region of tiles copied from a map."""
    width: int
    height: int
    # tiles[layer][y][x] - 9-bit (L1/L2) or 8-bit (L3) tile index
    tiles: list[list[list[int]]] = field(default_factory=list)
    # props[y][x] - 3-byte tuple (b0, b1, b2)
    tile_props: list[list[tuple[int, int, int]]] = field(default_factory=list)

    @classmethod
    def empty(cls) -> ClipboardRegion:
        return cls(width=0, height=0)

    def is_empty(self) -> bool:
        return self.width == 0 or self.height == 0


class MapClipboard:
    """Holds a single copied region and exposes paste operations."""

    def __init__(self) -> None:
        self._region: ClipboardRegion = ClipboardRegion.empty()
        self.paste_mode = PasteMode.ALL_LAYERS

    def copy(self, region: ClipboardRegion) -> None:
        self._region = region

    def is_empty(self) -> bool:
        return self._region.is_empty()

    @property
    def region(self) -> ClipboardRegion:
        return self._region

    def get_tile(self, layer: int, dx: int, dy: int) -> int | None:
        """Return tile at clipboard-relative (dx, dy) for *layer*, or None if OOB."""
        r = self._region
        if r.is_empty() or dy >= r.height or dx >= r.width:
            return None
        if not r.tiles or layer >= len(r.tiles):
            return None
        return r.tiles[layer][dy][dx]

    def get_props(self, dx: int, dy: int) -> tuple[int, int, int] | None:
        """Return tile-property bytes at clipboard-relative (dx, dy)."""
        r = self._region
        if r.is_empty() or dy >= r.height or dx >= r.width:
            return None
        if not r.tile_props:
            return (0, 0, 0)
        return r.tile_props[dy][dx]
