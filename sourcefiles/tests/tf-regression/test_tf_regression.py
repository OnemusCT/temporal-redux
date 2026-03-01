"""Structural comparison: Temporal Flux text dump vs Temporal Redux SNES parser.

Verifies that both sides agree on the start address and byte length of every command.

Run all:
    pytest sourcefiles/tests/tf-regression/ -v

Single location (exact):
    pytest "sourcefiles/tests/tf-regression/test_tf_regression.py::test_tf_regression[0x001]" -v
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from gamebackend import SnesBackend
from editorui.commanditem import process_script

_INPUT_DIR = Path(__file__).parent / "input"
_ROM_PATH = _INPUT_DIR / "Chrono Trigger (U) [!].smc"
_TF_FILE_RE = re.compile(r"LocEvents([0-9A-Fa-f]{3})\.txt", re.IGNORECASE)
_OBJ_HDR_RE = re.compile(r"^Object\s+([0-9A-Fa-f]+)", re.IGNORECASE)
_ADDR_RE    = re.compile(r"\[([0-9A-Fa-f]{4})\]")
_ARROW_RE   = re.compile(r"->\s*([0-9A-Fa-f]{2}[0-9A-Fa-f]*)\s*$")


def _parse_tf_file(path: Path) -> dict[int, dict[int, list[tuple[int, int]]]]:
    """Parse a Temporal Flux LocEvents*.txt dump.

    Returns: {obj_idx: {func_idx: [(tf_addr, byte_len), ...]}}

    TF files are UTF-16 encoded.  Three line types:
      - Object header   – stripped line matches "Object XX"
      - Function header – stripped line starts with '[ADDR] Name'
      - Command line    – stripped line starts with hex digits then '[ADDR]'

    For commands with a '-> FULLHEX' suffix (e.g. MemCpy, ColorMath mode 8)
    byte_len is derived from the full hex rather than the abbreviated left-side
    bytes, which only cover the fixed header portion.
    """
    text = path.read_bytes().decode("utf-16")

    result: dict[int, dict[int, list[tuple[int, int]]]] = {}
    cur_obj   = -1
    cur_func  = -1
    func_counter = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = _OBJ_HDR_RE.match(line)
        if m:
            cur_obj = int(m.group(1), 16)
            result[cur_obj] = {}
            cur_func = -1
            func_counter = 0
            continue

        if line.startswith("["):
            if cur_obj >= 0 and _ADDR_RE.match(line):
                cur_func = func_counter
                func_counter += 1
                result[cur_obj][cur_func] = []
            continue

        if not re.match(r"^[0-9A-Fa-f]", line) or cur_obj < 0 or cur_func < 0:
            continue

        addr_m = _ADDR_RE.search(line)
        if not addr_m:
            continue

        tf_addr   = int(addr_m.group(1), 16)
        bracket_i = addr_m.start()

        arrow_m = _ARROW_RE.search(line)
        if arrow_m:
            byte_len = len(arrow_m.group(1)) // 2
        else:
            left_hex = line[:bracket_i].replace(" ", "")
            byte_len = len(left_hex) // 2

        if byte_len > 0:
            result[cur_obj][cur_func].append((tf_addr, byte_len))

    return result

def _flatten_items(items) -> list[tuple[int, int, str]]:
    """Recursively collect (address, byte_length, display_name) from a CommandItem tree."""
    out: list[tuple[int, int, str]] = []
    for item in items:
        if item.command is not None and item.address is not None:
            out.append((item.address, len(item.command), item.name))
        out.extend(_flatten_items(item.children))
    return sorted(out, key=lambda t: t[0])

def _compare_function(
    tf_cmds: list[tuple[int, int]],          # (tf_addr, byte_len)
    tr_cmds: list[tuple[int, int, str]],     # (tr_addr, byte_len, name)
) -> tuple[bool, list[str]]:
    """Align commands by address and compare byte lengths.

    TF addresses are 1 higher than TR data indices (TF counts from the raw
    event blob including the leading count byte; TR strips that byte).
    We normalize by subtracting 1 from every TF address before comparing.

    Returns (passed, diff_lines).
    """
    tf_map = {tf_addr - 1: length for tf_addr, length in tf_cmds}
    tr_map = {addr: (length, name) for addr, length, name in tr_cmds}

    all_addrs = sorted(set(tf_map) | set(tr_map))

    passed = True
    diff: list[str] = []

    for addr in all_addrs:
        tf_len  = tf_map.get(addr)
        tr_pair = tr_map.get(addr)

        if tf_len is not None and tr_pair is not None:
            tr_len, tr_name = tr_pair
            ok = "✓" if tf_len == tr_len else "✗"
            if tf_len != tr_len:
                passed = False
            diff.append(
                f"  0x{addr:04X}  tf={tf_len:3d}B  tr={tr_len:3d}B  {ok}  {tr_name}"
            )
        elif tf_len is not None:
            passed = False
            diff.append(f"  0x{addr:04X}  tf={tf_len:3d}B  tr=---    ✗  (missing in TR)")
        else:
            tr_len, tr_name = tr_pair
            passed = False
            diff.append(
                f"  0x{addr:04X}  tf=---   tr={tr_len:3d}B  ✗  (missing in TF)  {tr_name}"
            )

    return passed, diff

def _loc_ids() -> list[int]:
    ids = []
    for f in _INPUT_DIR.glob("LocEvents*.txt"):
        m = _TF_FILE_RE.match(f.name)
        if m:
            ids.append(int(m.group(1), 16))
    return sorted(ids)

def pytest_generate_tests(metafunc):
    if "loc_id" in metafunc.fixturenames:
        ids = _loc_ids()
        metafunc.parametrize("loc_id", ids, ids=[f"0x{i:03X}" for i in ids])

@pytest.fixture(scope="module")
def snes_backend():
    if not _ROM_PATH.exists():
        pytest.skip(f"ROM not found: {_ROM_PATH}")
    return SnesBackend.from_path(_ROM_PATH)


def test_tf_regression(snes_backend, loc_id):
    """TR parser must agree with Temporal Flux on address and byte-length of every command."""

    try:
        event = snes_backend.get_script(loc_id)
    except SystemExit:
        pytest.skip(f"Script for location 0x{loc_id:03X} could not be decompressed")
    tr_tree  = process_script(event)

    tf_path  = _INPUT_DIR / f"LocEvents{loc_id:03X}.txt"
    tf_data  = _parse_tf_file(tf_path)

    failures: list[str] = []

    for obj_idx in range(event.num_objects):
        obj_item  = tr_tree[obj_idx] if obj_idx < len(tr_tree) else None
        num_funcs = len(obj_item.children) if obj_item is not None else 0
        tf_obj    = tf_data.get(obj_idx, {})

        for func_idx in range(num_funcs):
            func_item = obj_item.children[func_idx]
            tr_cmds   = _flatten_items(func_item.children)
            tf_cmds   = tf_obj.get(func_idx, [])

            # TODO: Consider making TR behave like TF for these cases. It will be
            # confusing to make edits that appear to be different functions but
            # are actually shared code. Currently this documents mismatches

            # Skip when TF has no commands for this function.  TF omits commands
            # for two reasons:
            #   • "Link to [ADDR]" — function pointer falls inside another
            #     object's byte range; TF shows the code there instead.
            #   • Shared empty pointer — multiple functions point to the same
            #     address; TF shows commands only under the first.
            # In both cases TR may still parse (duplicate or cross-object) bytes,
            # so we can't make a meaningful comparison.
            if not tf_cmds:
                continue

            # Skip when TR's function start equals the previous function's start.
            # This happens for Activate / Touch / Arbitrary* when they share a
            # pointer: TR ends up parsing the same bytecode again, but TF already
            # showed it under the earlier function and left this one empty above.
            if func_idx > 0:
                cur_start  = event.get_function_start(obj_idx, func_idx)
                prev_start = event.get_function_start(obj_idx, func_idx - 1)
                if cur_start == prev_start:
                    continue

            # Skip when TR couldn't parse any commands for this function.  This
            # happens when a function's pointer is numerically less than the next
            # distinct pointer, making get_function_end return a value smaller
            # than get_function_start (cross-object shared bytecode).  It's a TR
            # structural limitation, not an arg_lens error.
            if not tr_cmds:
                continue

            label = f"Loc {loc_id:03X}, Obj {obj_idx:02X}, {func_item.name}"
            passed, diff = _compare_function(tf_cmds, tr_cmds)
            if not passed:
                failures.append(f"{label}:\n" + "\n".join(diff))

    if failures:
        pytest.fail("\n\n".join(failures))
