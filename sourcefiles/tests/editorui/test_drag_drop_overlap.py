"""Regression test: drag-dropping a command into an If statement in a scene
that contains overlapping function pointers must not corrupt script.data.

The test ROM at tests/Chrono Trigger (U) [!].smc has an extra object added
to Scene 001 (Crono's Kitchen) — Object 0x10 — whose Function 0 contains
[If, ChangeLocation, Return] at the top level.

Root cause under investigation: get_function_end() scans ALL subsequent
pointer-table entries until it finds one that differs from the current
function's start address.  When newly-appended objects have several function
pointers sharing the same start address, functions from earlier objects can
end up with bytecode ranges that extend into those shared-pointer regions.
process_script() then creates duplicate CommandItem trees (same bytecode
address, different tree paths).  After _resync_all_jump_bytes() processes
these duplicates it writes conflicting jump-byte values to script.data,
corrupting If-jump-bytes for many unrelated objects.
"""

from pathlib import Path

import pytest
from PyQt6.QtCore import QModelIndex

from editorui.commanditem import CommandItem, process_script
from editorui.commanditemmodel import CommandModel, _get_all_commands
from jetsoftime.ctrom import CTRom
from jetsoftime.eventcommand import EventCommand

_TEST_ROM = Path(__file__).parent.parent / 'Chrono Trigger (U) [!].smc'
_LOC_ID = 1   # Scene 001 – Crono's Kitchen

class _MockBackend:
    """Minimal backend wrapper used so CommandModel can call script methods."""

    def __init__(self, event):
        self._event = event

    def get_script(self, _location_id: int):
        return self._event


def _compare_items(current_items, processed_items, path, discrepancies):
    """Recursively compare two CommandItem lists; collect discrepancies."""
    if len(current_items) != len(processed_items):
        discrepancies.append(
            f"Length mismatch at {' > '.join(path)}: "
            f"expected {len(processed_items)}, got {len(current_items)}"
        )
        return False

    is_match = True
    for current, processed in zip(current_items, processed_items):
        current_path = path + [current.name]
        if current.name != processed.name:
            discrepancies.append(
                f"Name mismatch at {' > '.join(current_path)}: "
                f"expected '{processed.name}', got '{current.name}'"
            )
            is_match = False

        if current.command != processed.command:
            discrepancies.append(
                f"Command mismatch at {' > '.join(current_path)}: "
                f"expected {processed.command}, got {current.command}"
            )
            is_match = False

        if current.address != processed.address:
            discrepancies.append(
                f"Address mismatch at {' > '.join(current_path)}: "
                f"expected 0x{processed.address:02X}, got 0x{current.address:02X}"
            )
            is_match = False
            return False

        if not _compare_items(
            current.children, processed.children, current_path, discrepancies
        ):
            is_match = False

    return is_match


def _build_model(ct_rom, loc_id: int):
    """Return (model, event) for loc_id, fully populated via change_location."""
    event = ct_rom.script_manager.get_script(loc_id)
    backend = _MockBackend(event)
    root = CommandItem("Root")
    model = CommandModel(root, backend=backend, location_id=loc_id)
    model.change_location(loc_id)
    return model, event


def _find_if_cl_return_func(model):
    """Find a function in the LAST tree-object whose top-level children are
    [conditional_cmd, change_location_cmd, anything].

    Returns (func_index, if_index, cl_index) or (None, None, None).
    """
    last_obj_row = model.rowCount(QModelIndex()) - 1
    last_obj_index = model.index(last_obj_row, 0, QModelIndex())

    for func_row in range(model.rowCount(last_obj_index)):
        func_index = model.index(func_row, 0, last_obj_index)
        if model.rowCount(func_index) < 2:
            continue
        child0 = model.index(0, 0, func_index).internalPointer()
        child1 = model.index(1, 0, func_index).internalPointer()
        if (child0.command is not None
                and child0.command.command in EventCommand.conditional_commands
                and child1.command is not None
                and child1.command.command in EventCommand.change_loc_commands):
            return (
                func_index,
                model.index(0, 0, func_index),
                model.index(1, 0, func_index),
            )
    return None, None, None

@pytest.fixture
def scene_001_ct_rom():
    if not _TEST_ROM.exists():
        pytest.skip(f"Test ROM not found: {_TEST_ROM}")
    return CTRom.from_file(str(_TEST_ROM), ignore_checksum=True)

def test_drag_drop_into_if_no_discrepancy(scene_001_ct_rom):
    """After dragging a ChangeLocation into an If statement in the last
    object's function, re-parsing script.data must produce the same tree
    structure — no discrepancies on every object in the scene.
    """
    model, event = _build_model(scene_001_ct_rom, _LOC_ID)

    func_index, if_index, cl_index = _find_if_cl_return_func(model)
    assert func_index is not None, (
        "Could not find a function with [If, ChangeLocation, ...] in the "
        "last object of Scene 001. Ensure the test ROM has an extra object "
        "with that structure."
    )

    if_item = if_index.internalPointer()
    cl_command = cl_index.internalPointer().command.copy()

    model.delete_command(cl_index)

    if_model_index = model.get_index_for_item(if_item)
    insert_address = if_item.address + len(if_item.command)
    model.insert_command(if_model_index, 0, cl_command, insert_address)

    processed = process_script(event)
    discrepancies = []
    match = _compare_items(
        model._root_item.children, processed, [], discrepancies
    )
    assert match, (
        "Tree discrepancies after drag-drop into If:\n"
        + "\n".join(f"  - {d}" for d in discrepancies)
    )


def test_resync_does_not_corrupt_unrelated_objects(scene_001_ct_rom):
    """Specifically verify that objects other than the last one are unaffected
    after the drag-drop + resync operation.

    This catches the scenario where get_function_end() overlap causes
    _resync_all_jump_bytes() to overwrite jump bytes for objects that were
    not modified at all.
    """
    model, event = _build_model(scene_001_ct_rom, _LOC_ID)

    func_index, if_index, cl_index = _find_if_cl_return_func(model)
    if func_index is None:
        pytest.skip(
            "Test ROM does not have the expected [If, ChangeLocation] "
            "function in the last object of Scene 001."
        )

    last_obj_row = model.rowCount(QModelIndex()) - 1
    if_item = if_index.internalPointer()
    cl_command = cl_index.internalPointer().command.copy()

    # Snapshot the jump-byte values for every conditional in objects 0..N-2
    # BEFORE the drag-drop
    before = {}
    for item in _get_all_commands(model._root_item):
        if (item.command is not None
                and item.command.command in EventCommand.conditional_commands
                and item.address is not None):
            # Only track items whose parent chain does NOT include the last object
            obj_item = item
            while obj_item.parent is not None and obj_item.parent != model._root_item:
                obj_item = obj_item.parent
            if model._root_item.children.index(obj_item) < last_obj_row:
                before[item.address] = item.command.args[-1]

    # Perform drag-drop
    model.delete_command(cl_index)
    if_model_index = model.get_index_for_item(if_item)
    model.insert_command(
        if_model_index, 0, cl_command,
        if_item.address + len(if_item.command)
    )
#    model._resync_all_jump_bytes()

    # Snapshot AFTER
    after = {}
    for item in _get_all_commands(model._root_item):
        if (item.command is not None
                and item.command.command in EventCommand.conditional_commands
                and item.address is not None):
            obj_item = item
            while obj_item.parent is not None and obj_item.parent != model._root_item:
                obj_item = obj_item.parent
            if model._root_item.children.index(obj_item) < last_obj_row:
                after[item.address] = item.command.args[-1]

    corrupted = {
        addr: (before[addr], after[addr])
        for addr in before
        if before[addr] != after.get(addr)
    }
    assert not corrupted, (
        "Jump bytes corrupted for unrelated objects after drag-drop:\n"
        + "\n".join(
            f"  addr=0x{a:04X}: was {v[0]}, now {v[1]}"
            for a, v in sorted(corrupted.items())
        )
    )