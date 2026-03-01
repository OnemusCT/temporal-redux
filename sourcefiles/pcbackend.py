from __future__ import annotations

import shutil
import struct
from pathlib import Path

from sourcefiles.jetsoftime import ctevent, ctstrings
from gamebackend import GameBackend
from pcgamedata import (
    GameData,
    MSG_TABLE_FILES,
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

# Maps PC tag names to CTString keyword syntax.
_PC_TAG_MAP: dict[str, str] = {
    'NAME_CRO': '{crono}',
    'NAME_MAR': '{marle}',
    'NAME_LUC': '{lucca}',
    'NAME_ROB': '{robo}',
    'NAME_FRO': '{frog}',
    'NAME_AYL': '{ayla}',
    'NAME_MAG': '{magus}',
    'NICK_CRO': '{crononick}',
    'PAGE':     '{page break}',
    'AUTO_PAGE':'{page break}',
}

# Characters (outside of tags) that CTString.from_ascii can handle directly.
_SAFE_CHARS = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    '0123456789'
    "!?.,:-+%=&()' "
)


_CT_KEYWORD_TO_PC: dict[str, str] = {
    '{crono}':      '<NAME_CRO>',
    '{marle}':      '<NAME_MAR>',
    '{lucca}':      '<NAME_LUC>',
    '{robo}':       '<NAME_ROB>',
    '{frog}':       '<NAME_FRO>',
    '{ayla}':       '<NAME_AYL>',
    '{magus}':      '<NAME_MAG>',
    '{crononick}':  '<NICK_CRO>',
    '{page break}': '<PAGE>',
    '{line break}': '\\',
}


def _ct_ascii_to_pc_str(s: str) -> str:
    """Translate CTString ASCII ({keyword} format) back to PC <Tag> format."""
    result: list[str] = []
    pos = 0
    while pos < len(s):
        if s[pos] == '{':
            end = s.find('}', pos)
            if end == -1:
                pos += 1
                continue
            keyword = s[pos:end + 1]
            if keyword.startswith('{delay '):
                hex_val = keyword[7:-1]
                result.append(f'<WAIT>{hex_val}</WAIT>')
            elif keyword in _CT_KEYWORD_TO_PC:
                result.append(_CT_KEYWORD_TO_PC[keyword])
            # Unknown keywords are silently dropped
            pos = end + 1
        else:
            result.append(s[pos])
            pos += 1
    return ''.join(result)


def _pc_str_to_ct_ascii(s: str) -> str:
    """Translate a PC (Steam) message string to CTString-compatible ASCII.

    PC strings use <TAG> syntax and backslash line breaks; CTString uses
    {keyword} syntax.  Unknown or structural tags are silently dropped.
    """
    result: list[str] = []
    pos = 0
    while pos < len(s):
        ch = s[pos]
        if ch == '<':
            end = s.find('>', pos)
            if end == -1:
                pos += 1
                continue
            tag = s[pos + 1:end]
            if tag.startswith('WAIT'):
                # <WAIT>HH</WAIT> — extract the hex delay value between the tags
                inner_start = end + 1
                close = s.find('</WAIT>', inner_start)
                if close != -1:
                    hex_val = s[inner_start:close].strip()
                    result.append(f'{{delay {hex_val}}}')
                    pos = close + len('</WAIT>')
                else:
                    pos = end + 1
            elif tag in _PC_TAG_MAP:
                result.append(_PC_TAG_MAP[tag])
                pos = end + 1
            else:
                # Closing tags (</...>) and unknown tags are skipped.
                pos = end + 1
        elif ch == '\\':
            result.append('{line break}')
            pos += 1
        elif ch in _SAFE_CHARS:
            result.append(ch)
            pos += 1
        else:
            pos += 1
    return ''.join(result)


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
            translated = _pc_str_to_ct_ascii(s) or '?'
            try:
                ct_strings.append(ctstrings.CTString.from_ascii(translated))
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

    def modify_string(self, loc_id: int, string_idx: int, new_ascii: str) -> None:
        event = self.get_script(loc_id)
        if string_idx >= len(event.strings):
            return
        event.strings[string_idx] = ctstrings.CTString.from_ascii(new_ascii)

        if self._gd.is_archive:
            return  # read-only archive — in-memory update only

        table_idx = event.get_string_index()
        if table_idx is None:
            return
        self._rewrite_string_table(table_idx, string_idx, _ct_ascii_to_pc_str(new_ascii))

    def _rewrite_string_table(self, table_idx: int, string_idx: int, new_pc_str: str) -> None:
        fname = MSG_TABLE_FILES[table_idx]
        vpath = f"{self._msg_prefix}/{fname}"
        raw = self._gd.read(vpath)
        lines = raw.decode('utf-8').splitlines()
        if string_idx < len(lines):
            line = lines[string_idx]
            key = line.split(',', 1)[0] if ',' in line else ''
            lines[string_idx] = f"{key},{new_pc_str}" if key else new_pc_str
        self._gd.write(vpath, '\n'.join(lines).encode('utf-8'))

    @property
    def platform(self) -> str:
        return 'pc'

    @property
    def is_read_only(self) -> bool:
        return self._gd.is_archive
