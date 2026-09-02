"""Parses Practice ROM memory-dump text files (see e.g. `Practice States/JP/`)
into structured address/byte chunks.

Each file documents one visit to one location. The filename carries the location
id; the file body is a short freeform header line followed by one or more
raw-memory chunk lines:

    070 Truce_Bird  from Truce_Gate  Story:0c
    0x2400,d6000000...
    0x2600,0086804600...
    ...

Filename convention: "<hex location id>[-<variant>].txt", e.g. "070.txt" or
"070-MIDROOM.txt". A location's save state is a single fixed set of Mem Copy
commands, so a variant suffix marks a secondary state for the same location.

Header line: freeform, written by whoever captured the dump (previous
location, story counter at the time). Never parsed for values -- kept
verbatim only so callers can show it in a report.

Chunk lines: "0x<offset>,<hex bytes>". `offset` is relative to $7E0000 (SNES
low RAM), so values at or past 0x10000 land in bank $7F -- e.g. offset
0x10021 is address $7F0021, the practice-hack guard flag itself (see
scanner.PRACTICE_FLAG_ADDRESS). `hex bytes` is the raw memory read starting
at that address, with no separators between bytes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

WRAM_BASE_ADDRESS = 0x7E0000

_FILENAME_PATTERN = re.compile(r'^(?P<location_id>[0-9a-fA-F]+)(?:-(?P<variant>.+))?$')
_CHUNK_LINE_PATTERN = re.compile(r'^0x(?P<offset>[0-9a-fA-F]+),(?P<hex_bytes>[0-9a-fA-F]*)$')


class DumpParseError(ValueError):
    """A dump file's contents don't match the expected chunk-line format."""


@dataclass
class MemoryDumpChunk:
    """One captured run of contiguous WRAM bytes, starting at `address`
    (already resolved to an absolute $7Exxxx/$7Fxxxx address)."""
    address: int
    data: bytes


@dataclass
class LocationDump:
    """Everything parsed from one dump file."""
    location_id: int
    variant: str | None
    header: str
    source_path: Path
    chunks: list[MemoryDumpChunk]


@dataclass
class DumpLoadResult:
    """Outcome of scanning a whole directory of dump files."""
    dumps: list[LocationDump] = field(default_factory=list)
    # Files whose name doesn't look like a dump at all (e.g. a walkthrough
    # index like "Log.txt") -- not an error, just not this module's concern.
    ignored: list[Path] = field(default_factory=list)
    # Files that looked like a dump by name but failed to parse.
    errors: list[tuple[Path, str]] = field(default_factory=list)


def parse_dump_filename(path: Path) -> tuple[int, str | None] | None:
    """(location_id, variant) from `path`'s filename, or None if the name
    isn't of the form "<hex location id>[-<variant>].txt"."""
    match = _FILENAME_PATTERN.match(path.stem)
    if match is None:
        return None
    try:
        location_id = int(match.group('location_id'), 16)
    except ValueError:
        return None
    return location_id, match.group('variant')


def parse_dump_file(path: Path) -> LocationDump:
    """Parse one dump file. Raises DumpParseError if its name or body don't
    match the expected format."""
    parsed_name = parse_dump_filename(path)
    if parsed_name is None:
        raise DumpParseError(
            f"{path.name}: filename is not of the form <hex location id>[-variant].txt"
        )
    location_id, variant = parsed_name

    lines = path.read_text(encoding='utf-8').splitlines()
    header = lines[0].strip() if lines else ''
    chunks = [
        chunk for chunk in (_parse_chunk_line(line, path) for line in lines[1:])
        if chunk is not None
    ]
    return LocationDump(location_id, variant, header, path, chunks)


def _parse_chunk_line(line: str, path: Path) -> MemoryDumpChunk | None:
    stripped = line.strip()
    if not stripped:
        return None

    match = _CHUNK_LINE_PATTERN.match(stripped)
    if match is None:
        raise DumpParseError(f"{path.name}: malformed dump line {stripped!r}")

    offset = int(match.group('offset'), 16)
    hex_bytes = match.group('hex_bytes')
    if len(hex_bytes) % 2 != 0:
        raise DumpParseError(f"{path.name}: odd number of hex digits in {stripped!r}")

    return MemoryDumpChunk(WRAM_BASE_ADDRESS + offset, bytes.fromhex(hex_bytes))


def load_dump_directory(directory: Path) -> DumpLoadResult:
    """Parse every *.txt file directly in `directory` (non-recursive)."""
    result = DumpLoadResult()
    for path in sorted(directory.glob('*.txt')):
        if parse_dump_filename(path) is None:
            result.ignored.append(path)
            continue
        try:
            result.dumps.append(parse_dump_file(path))
        except DumpParseError as error:
            result.errors.append((path, str(error)))
    return result
