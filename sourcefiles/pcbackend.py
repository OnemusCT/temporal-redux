from __future__ import annotations

import shutil
import struct
from pathlib import Path

from sourcefiles.jetsoftime import ctevent, ctstrings
from gamebackend import GameBackend
from pcgamedata import (
    GameData,
    read_scene_script_raw,
    load_string_table,
    discover_msg_prefix,
    _SCRIPT_INDEX_OFFSET,
    _MAP_INDEX_OFFSET,
)


# Maximum scene index to probe when building the location list.
_MAX_SCENE_PROBE = 600

# Stop scanning after this many consecutive missing mapinfo files.
_MISS_LIMIT = 10


class PcBackend(GameBackend):
    def __init__(self, path: Path):
        self._gd = GameData(str(path))
        self._script_cache: dict[int, ctevent.Event] = {}
        # scene_index -> script_index (from mapinfo header)
        self._scene_to_script: dict[int, int] = {}
        self._location_list: list[tuple[int, str]] = []
        self._msg_prefix: str | None = discover_msg_prefix(self._gd)
        self._build_location_list()

    def _attach_strings(self, event: ctevent.Event) -> None:
        if self._msg_prefix is None:
            return

        table_idx = event.get_string_index()
        if table_idx is None:
            return

        raw_strings = load_string_table(self._gd, self._msg_prefix, table_idx)
        if raw_strings is None:
            return

        ct_strings: list[ctstrings.CTString] = []
        for s in raw_strings:
            safe = ''.join(c for c in s if c.isascii() and c.isprintable()) or '?'
            try:
                ct_strings.append(ctstrings.CTString.from_ascii(safe))
            except Exception:
                ct_strings.append(ctstrings.CTString.from_ascii('?'))

        event.strings = ct_strings

    def _build_location_list(self) -> None:
        consecutive_misses = 0
        for scene_index in range(_MAX_SCENE_PROBE):
            vpath = f"Game/field/Mapinfo/mapinfo_{scene_index}.dat"
            if not self._gd.exists(vpath):
                consecutive_misses += 1
                if consecutive_misses >= _MISS_LIMIT:
                    break
                continue

            consecutive_misses = 0
            try:
                raw = self._gd.read(vpath)
                if len(raw) < 18:
                    continue
                script_index = struct.unpack_from('<H', raw, _SCRIPT_INDEX_OFFSET)[0]
                map_index    = struct.unpack_from('<H', raw, _MAP_INDEX_OFFSET)[0]
                self._scene_to_script[scene_index] = script_index
                name = f"Scene {scene_index:04d}  (map={map_index}, script={script_index})"
                self._location_list.append((scene_index, name))
            except Exception:
                pass

    def get_script(self, location_id: int) -> ctevent.Event:
        if location_id in self._script_cache:
            return self._script_cache[location_id]

        script_index = self._scene_to_script[location_id]
        raw = read_scene_script_raw(self._gd, script_index)
        event = ctevent.Event.from_pc_data(raw)
        self._attach_strings(event)
        self._script_cache[location_id] = event
        return event

    def get_location_list(self) -> list[tuple[int, str]]:
        return list(self._location_list)

    def write_script(self, location_id: int) -> None:
        if self._gd.is_archive:
            return
        script_index = self._scene_to_script[location_id]
        event = self._script_cache[location_id]
        vpath = f"Game/field/atel/Atel_{script_index:04d}.dat"
        self._gd.write(vpath, bytes(event.get_bytearray()))

    def save_to_file(self, path: Path) -> None:
        if self._gd.is_archive:
            return
        src = Path(self._gd.directory).resolve()
        dst = path.resolve()
        if src == dst:
            return  # already written in-place by write_script
        if dst.is_relative_to(src):
            raise ValueError(f"Destination {dst} is inside source {src}")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    @property
    def platform(self) -> str:
        return 'pc'

    @property
    def is_read_only(self) -> bool:
        return self._gd.is_archive
