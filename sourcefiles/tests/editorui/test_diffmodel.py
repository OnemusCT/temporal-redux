"""Tests for the DiffModel Qt model."""
import pytest
from PyQt6.QtCore import Qt

from jetsoftime.eventcommand import EventCommand, Platform
from jetsoftime.byteops import to_little_endian
from jetsoftime.ctevent import Event
from editorui.eventdiff import compute_location_diff, DiffStatus
from editorui.diffmodel import DiffModel, DiffColumn, _COLOR_EQUAL, _COLOR_MODIFIED


def _build_event(
    num_objects: int,
    functions: dict[tuple[int, int], list[EventCommand]],
    platform: Platform = Platform.SNES,
) -> Event:
    """Build a minimal Event (same helper as in test_eventdiff.py)."""
    func_bytes: dict[tuple[int, int], bytearray] = {}
    for key, cmds in functions.items():
        data = bytearray()
        for cmd in cmds:
            data.extend(cmd.to_bytearray())
        func_bytes[key] = data

    ptr_table_size = num_objects * 32
    bytecode = bytearray()
    func_offsets: dict[tuple[int, int], int] = {}

    for obj_id in range(num_objects):
        for func_id in range(16):
            key = (obj_id, func_id)
            if key in func_bytes:
                func_offsets[key] = ptr_table_size + len(bytecode)
                bytecode.extend(func_bytes[key])

    end_offset = ptr_table_size + len(bytecode)
    ptr_table = bytearray(ptr_table_size)
    for obj_id in range(num_objects):
        for func_id in range(16):
            key = (obj_id, func_id)
            if key in func_offsets:
                offset = func_offsets[key]
            else:
                offset = end_offset
                for fid in range(func_id, 16):
                    if (obj_id, fid) in func_offsets:
                        offset = func_offsets[(obj_id, fid)]
                        break
            ptr_pos = obj_id * 32 + func_id * 2
            ptr_table[ptr_pos:ptr_pos + 2] = to_little_endian(offset, 2)

    event = Event()
    event.num_objects = num_objects
    event.data = ptr_table + bytecode
    event.platform = platform
    event.strings = []
    return event


def _make_diff_model(left_funcs, right_funcs, num_objects=1, platform=Platform.SNES):
    """Convenience: build two events, compute diff, populate model."""
    left = _build_event(num_objects, left_funcs, platform)
    right = _build_event(num_objects, right_funcs, platform)
    diff = compute_location_diff(left, right, 0)
    model = DiffModel()
    model.set_diff(diff)
    return model, diff


class TestEmptyModel:
    def test_no_diff_set(self):
        model = DiffModel()
        assert model.rowCount() == 0
        assert model.columnCount() == 5

    def test_empty_diff(self, qtmodeltester):
        cmds = [EventCommand.return_cmd()]
        model, diff = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})
        qtmodeltester.check(model)


class TestRowCounts:
    def test_top_level_row_count(self):
        cmds_a = [EventCommand.script_speed(1), EventCommand.return_cmd()]
        cmds_b = [EventCommand.set_speed(2), EventCommand.return_cmd()]
        model, diff = _make_diff_model(
            {(0, 0): cmds_a, (0, 1): cmds_b},
            {(0, 0): cmds_a, (0, 1): cmds_b},
        )
        # One FunctionDiff per non-empty function
        assert model.rowCount() == len(diff.functions)

    def test_child_row_count(self):
        left_cmds = [EventCommand.script_speed(1), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(2), EventCommand.return_cmd()]
        model, diff = _make_diff_model({(0, 0): left_cmds}, {(0, 0): right_cmds})

        parent = model.index(0, 0)
        assert model.rowCount(parent) == len(diff.functions[0].lines)


class TestDisplayData:
    def test_header_row_shows_function_name(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        idx = model.index(0, DiffColumn.LEFT_COMMAND)
        text = model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "Object 00" in text
        assert "Startup" in text

    def test_child_left_address(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, DiffColumn.LEFT_ADDRESS, parent)
        text = model.data(child, Qt.ItemDataRole.DisplayRole)
        assert text.startswith("0x")

    def test_child_right_address(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, DiffColumn.RIGHT_ADDRESS, parent)
        text = model.data(child, Qt.ItemDataRole.DisplayRole)
        assert text.startswith("0x")

    def test_child_status_symbol_equal(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, DiffColumn.STATUS, parent)
        text = model.data(child, Qt.ItemDataRole.DisplayRole)
        assert text == "="

    def test_child_status_symbol_modified(self):
        model, _ = _make_diff_model(
            {(0, 0): [EventCommand.script_speed(1), EventCommand.return_cmd()]},
            {(0, 0): [EventCommand.script_speed(2), EventCommand.return_cmd()]},
        )
        parent = model.index(0, 0)
        # Find the modified line
        for row in range(model.rowCount(parent)):
            idx = model.index(row, DiffColumn.STATUS, parent)
            if model.data(idx, Qt.ItemDataRole.DisplayRole) == "~":
                return  # found it
        pytest.fail("No modified status symbol found")

    def test_left_only_has_empty_right(self):
        model, _ = _make_diff_model(
            {(0, 0): [EventCommand.script_speed(1), EventCommand.return_cmd()]},
            {(0, 0): [EventCommand.return_cmd()]},
        )
        parent = model.index(0, 0)
        for row in range(model.rowCount(parent)):
            status_idx = model.index(row, DiffColumn.STATUS, parent)
            if model.data(status_idx, Qt.ItemDataRole.DisplayRole) == "<":
                right_cmd = model.index(row, DiffColumn.RIGHT_COMMAND, parent)
                assert model.data(right_cmd, Qt.ItemDataRole.DisplayRole) == ""
                right_addr = model.index(row, DiffColumn.RIGHT_ADDRESS, parent)
                assert model.data(right_addr, Qt.ItemDataRole.DisplayRole) == ""
                return
        pytest.fail("No left-only line found")


class TestBackgroundColors:
    def test_equal_line_green(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, DiffColumn.LEFT_COMMAND, parent)
        bg = model.data(child, Qt.ItemDataRole.BackgroundRole)
        assert bg == _COLOR_EQUAL

    def test_modified_line_yellow(self):
        model, _ = _make_diff_model(
            {(0, 0): [EventCommand.script_speed(1), EventCommand.return_cmd()]},
            {(0, 0): [EventCommand.script_speed(2), EventCommand.return_cmd()]},
        )
        parent = model.index(0, 0)
        for row in range(model.rowCount(parent)):
            idx = model.index(row, DiffColumn.STATUS, parent)
            if model.data(idx, Qt.ItemDataRole.DisplayRole) == "~":
                bg = model.data(
                    model.index(row, DiffColumn.LEFT_COMMAND, parent),
                    Qt.ItemDataRole.BackgroundRole,
                )
                assert bg == _COLOR_MODIFIED
                return
        pytest.fail("No modified line found")

    def test_identical_function_header_green(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        idx = model.index(0, 0)
        bg = model.data(idx, Qt.ItemDataRole.BackgroundRole)
        assert bg == _COLOR_EQUAL

    def test_different_function_header_yellow(self):
        model, _ = _make_diff_model(
            {(0, 0): [EventCommand.script_speed(1), EventCommand.return_cmd()]},
            {(0, 0): [EventCommand.script_speed(2), EventCommand.return_cmd()]},
        )
        idx = model.index(0, 0)
        bg = model.data(idx, Qt.ItemDataRole.BackgroundRole)
        assert bg == _COLOR_MODIFIED


class TestHeaders:
    def test_column_headers(self):
        model = DiffModel()
        for col in range(5):
            header = model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            assert header is not None

    def test_column_count(self):
        model = DiffModel()
        assert model.columnCount() == 5


class TestAccessors:
    def test_get_diff_line_on_child(self):
        cmds = [EventCommand.return_cmd()]
        model, diff = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, 0, parent)
        dl = model.get_diff_line(child)
        assert dl is not None
        assert dl.status == DiffStatus.EQUAL

    def test_get_diff_line_on_header_returns_none(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        idx = model.index(0, 0)
        assert model.get_diff_line(idx) is None

    def test_get_function_diff_on_header(self):
        cmds = [EventCommand.return_cmd()]
        model, diff = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        idx = model.index(0, 0)
        fd = model.get_function_diff(idx)
        assert fd is not None
        assert fd.function_name == "Startup / Idle"

    def test_get_function_diff_on_child_returns_none(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, 0, parent)
        assert model.get_function_diff(child) is None


class TestModelConsistency:
    def test_qtmodeltester_identical(self, qtmodeltester):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})
        qtmodeltester.check(model)

    def test_qtmodeltester_with_diffs(self, qtmodeltester):
        model, _ = _make_diff_model(
            {(0, 0): [EventCommand.script_speed(1), EventCommand.return_cmd()]},
            {(0, 0): [EventCommand.script_speed(2), EventCommand.set_speed(3), EventCommand.return_cmd()]},
        )
        qtmodeltester.check(model)

    def test_qtmodeltester_multi_object(self, qtmodeltester):
        cmds_a = [EventCommand.script_speed(1), EventCommand.return_cmd()]
        cmds_b = [EventCommand.return_cmd()]
        model, _ = _make_diff_model(
            {(0, 0): cmds_a, (1, 0): cmds_b},
            {(0, 0): cmds_b},
            num_objects=2,
        )
        qtmodeltester.check(model)

    def test_parent_child_navigation(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        # Top level has no parent
        top = model.index(0, 0)
        assert not model.parent(top).isValid()

        # Child's parent is the top-level row
        child = model.index(0, 0, top)
        parent_of_child = model.parent(child)
        assert parent_of_child.isValid()
        assert parent_of_child.row() == 0


class TestTooltips:
    def test_no_tooltip_when_copyable(self):
        cmds = [EventCommand.return_cmd()]
        model, _ = _make_diff_model({(0, 0): cmds}, {(0, 0): cmds})

        parent = model.index(0, 0)
        child = model.index(0, 0, parent)
        tip = model.data(child, Qt.ItemDataRole.ToolTipRole)
        assert tip is None

    def test_tooltip_when_read_only(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})
        diff = compute_location_diff(left, right, 0, right_read_only=True)

        model = DiffModel()
        model.set_diff(diff)

        parent = model.index(0, 0)
        child = model.index(0, 0, parent)
        tip = model.data(child, Qt.ItemDataRole.ToolTipRole)
        assert tip is not None
        assert "read-only" in tip.lower()
