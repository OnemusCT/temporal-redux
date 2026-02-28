"""
PC (Steam) game data loading infrastructure.

Handles the resources.bin encrypted archive format or an extracted directory
laid out as Game/ and Localize/ sub-trees.
"""
from __future__ import annotations

import io
import os
import struct
import zlib

_LCG_BASE = 0x19000000   # BASE_SEED (i32)
_LCG_VAL1 = 0x41C64E6D  # multiplier (i32)
_LCG_VAL2 = 12345        # increment  (i32)


def _to_i32(v: int) -> int:
    """Truncate a Python int to a signed 32-bit integer (wrapping)."""
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _xor_decrypt(data: bytes, block_seed: int) -> bytes:
    """XOR-decrypt a block using the LCG keystream."""
    num1 = _to_i32(_LCG_BASE + block_seed)
    out = bytearray(len(data))
    for i, b in enumerate(data):
        num1 = _to_i32(num1 * _LCG_VAL1 + _LCG_VAL2)
        out[i] = b ^ ((num1 >> 24) & 0xFF)
    return bytes(out)


def _decrypt_then_decompress(data: bytes, block_seed: int) -> bytes:
    """
    Decrypt with LCG then strip the 4-byte big-endian decompressed-length
    prefix and gzip-decompress.
    """
    decrypted = _xor_decrypt(data, block_seed)
    decompressed_len = struct.unpack_from('>I', decrypted, 0)[0]
    decompressed = zlib.decompress(decrypted[4:], wbits=47)
    return decompressed[:decompressed_len]

class ResourcesBin:
    """
    Reader for the Steam version's resources.bin container.

    Format (XOR+gzip encrypted at seed 0):
      Header (16 bytes):
        [0..4]   "ARC1" signature
        [4..8]   u32 LE  total file length
        [8..12]  u32 LE  directory offset
        [12..16] u32 LE  directory compressed length

      Directory (XOR+gzip, seed = directory_offset):
        u32 LE  file_count
        file_count × { u32 path_offset, u32 file_offset, u32 file_size }
        null-terminated path strings

      Each file (XOR+gzip, seed = file_offset)
    """

    def __init__(self, bin_path: str):
        self.bin_path = bin_path
        self._index: dict[str, tuple[int, int]] = {}  # path -> (offset, size)
        self._load_directory()

    def _load_directory(self):
        with open(self.bin_path, 'rb') as f:
            raw_header = f.read(16)
        header = _xor_decrypt(raw_header, 0)
        sig = header[0:4]
        if sig != b'ARC1':
            raise ValueError(f"Not a resources.bin: bad signature {sig!r}")
        dir_offset = struct.unpack_from('<I', header, 8)[0]
        dir_length = struct.unpack_from('<I', header, 12)[0]

        with open(self.bin_path, 'rb') as f:
            f.seek(dir_offset)
            raw_dir = f.read(dir_length)
        dir_data = _decrypt_then_decompress(raw_dir, _to_i32(dir_offset))

        file_count = struct.unpack_from('<I', dir_data, 0)[0]
        entries = []
        pos = 4
        for _ in range(file_count):
            path_off, file_off, file_sz = struct.unpack_from('<III', dir_data, pos)
            entries.append((path_off, file_off, file_sz))
            pos += 12

        for path_off, file_off, file_sz in entries:
            end = dir_data.index(0, path_off)
            path_str = dir_data[path_off:end].decode('utf-8')
            self._index[path_str] = (file_off, file_sz)

    def file_exists(self, path: str) -> bool:
        return path in self._index

    def file_get(self, path: str) -> bytes:
        if path not in self._index:
            raise FileNotFoundError(f"Not in resources.bin: {path}")
        file_off, file_sz = self._index[path]
        with open(self.bin_path, 'rb') as f:
            f.seek(file_off)
            raw = f.read(file_sz)
        return _decrypt_then_decompress(raw, _to_i32(file_off))

    def list_files(self) -> list[str]:
        return sorted(self._index.keys())


class GameData:
    """
    Unified file reader for either a resources.bin archive or an extracted
    directory containing Game/ and Localize/ sub-trees.
    """

    def __init__(self, path: str):
        if os.path.isfile(path) and path.lower().endswith('.bin'):
            self._bin = ResourcesBin(path)
            self._dir = None
        elif os.path.isdir(path):
            self._bin = None
            self._dir = path
        else:
            raise FileNotFoundError(f"Path not found or not recognised: {path}")

    @property
    def is_archive(self) -> bool:
        return self._bin is not None

    @property
    def directory(self) -> str | None:
        """The root directory path, or None if backed by an archive."""
        return self._dir

    def read(self, virtual_path: str) -> bytes:
        """Read a file by its virtual path (forward slashes normalised)."""
        virtual_path = virtual_path.replace('\\', '/')
        if self._bin is not None:
            return self._bin.file_get(virtual_path)
        fs_path = os.path.join(self._dir, *virtual_path.split('/'))
        with open(fs_path, 'rb') as f:
            return f.read()

    def exists(self, virtual_path: str) -> bool:
        virtual_path = virtual_path.replace('\\', '/')
        if self._bin is not None:
            return self._bin.file_exists(virtual_path)
        fs_path = os.path.join(self._dir, *virtual_path.split('/'))
        return os.path.exists(fs_path)

    def write(self, virtual_path: str, data: bytes) -> None:
        """Write data to a file by its virtual path. Only supported for directory-backed instances."""
        if self._bin is not None:
            raise RuntimeError("Cannot write to a resources.bin archive.")
        virtual_path = virtual_path.replace('\\', '/')
        fs_path = os.path.join(self._dir, *virtual_path.split('/'))
        os.makedirs(os.path.dirname(fs_path), exist_ok=True)
        with open(fs_path, 'wb') as f:
            f.write(data)

# Mapinfo u16 field offsets (each field is 2 bytes):
#   0: music_index, 2: tileset_l12, 4: tileset_l12_assembly, 6: tileset_l3,
#   8: palette, 10: palette_anims, 12: map_index, 14: chip_anims,
#   16: script_index, 18: unknown
_MAP_INDEX_OFFSET    = 12
_SCRIPT_INDEX_OFFSET = 16


def read_scene_header(gd: GameData, scene_index: int) -> dict:
    """Read the mapinfo header for a given scene index."""
    raw = gd.read(f"Game/field/Mapinfo/mapinfo_{scene_index}.dat")
    return {
        'music_index':    struct.unpack_from('<H', raw, 0)[0],
        'map_index':      struct.unpack_from('<H', raw, _MAP_INDEX_OFFSET)[0],
        'script_index':   struct.unpack_from('<H', raw, _SCRIPT_INDEX_OFFSET)[0],
        'scroll_left':    raw[20],
        'scroll_top':     raw[21],
        'scroll_right':   raw[22],
        'scroll_bottom':  raw[23],
    }


def read_scene_script_raw(gd: GameData, script_index: int) -> bytes:
    """Return the raw bytes of Atel_{script_index:04d}.dat."""
    return gd.read(f"Game/field/atel/Atel_{script_index:04d}.dat")

MSG_TABLE_FILES: list[str] = [
    "cmes0.txt", "cmes1.txt", "cmes2.txt", "cmes3.txt", "cmes4.txt", "cmes5.txt",
    "kmes0.txt", "kmes1.txt", "kmes2.txt",
    "mesi0.txt",
    "mesk0.txt", "mesk1.txt", "mesk2.txt", "mesk3.txt", "mesk4.txt",
    "mess0.txt",
    "mest0.txt", "mest1.txt", "mest2.txt", "mest3.txt", "mest4.txt", "mest5.txt",
    "msg01.txt", "msg02.txt", "msg03.txt", "msg04.txt",
    "exms0.txt", "exms1.txt", "exms2.txt", "exms3.txt",
    "wireless1.txt", "wireless2.txt",
]


def discover_msg_prefix(gd: GameData) -> str | None:
    """
    Probe common virtual-path patterns to find where message (*.txt) files live.

    The Steam release stores messages under Localize/<lang>/msg/, but the
    exact language code varies.  Returns a prefix string such as
    "Localize/us/msg" that can be joined with a filename, or None if no
    message files are found.
    """
    _PROBE = "cmes0.txt"
    _LANGS = ('us', 'en', 'jp', 'kr', 'cn', 'tw', 'fr', 'de', 'it', 'es', 'pt')

    # Standard pattern: Localize/<lang>/msg/<file>
    for lang in _LANGS:
        prefix = f"Localize/{lang}/msg"
        if gd.exists(f"{prefix}/{_PROBE}"):
            return prefix

    # Fallback: Localize/<lang>/<file>  (no msg subdir)
    for lang in _LANGS:
        prefix = f"Localize/{lang}"
        if gd.exists(f"{prefix}/{_PROBE}"):
            return prefix

    # Fallback: Localize/msg/<file>  (no lang subdir)
    if gd.exists(f"Localize/msg/{_PROBE}"):
        return "Localize/msg"

    # Fallback: Localize/<file>
    if gd.exists(f"Localize/{_PROBE}"):
        return "Localize"

    return None


def load_string_table(gd: GameData, msg_prefix: str, table_index: int) -> list[str] | None:
    """
    Load a message table and return a list of strings (key prefix stripped).

    msg_prefix is the virtual-path prefix returned by discover_msg_prefix(),
    e.g. "Localize/us/msg".  Returns None if the file does not exist.
    """
    if table_index >= len(MSG_TABLE_FILES):
        return None
    fname = MSG_TABLE_FILES[table_index]
    vpath = f"{msg_prefix}/{fname}"
    if not gd.exists(vpath):
        return None
    raw = gd.read(vpath)
    strings = []
    for line in raw.decode('utf-8', errors='replace').splitlines():
        if ',' in line:
            strings.append(line.split(',', 1)[1])
        else:
            strings.append(line)
    return strings
