import pytest
from PyQt6.QtCore import QModelIndex, Qt

from editorui.commanditem import CommandItem
from editorui.commanditemmodel import CommandModel
from jetsoftime.eventcommand import EventCommand
from jetsoftime.ctevent import Event

class _MockBackend:
    def __init__(self, event: Event):
        self._event = event
    def get_script(self, location_id: int) -> Event:
        return self._event

def _build_minimal_event() -> Event:
    event = Event()
    event.num_objects = 1
    data = bytearray(32)
    for i in range(16):
        data[2 * i] = 32
        data[2 * i + 1] = 0
    data.extend(bytearray([0x0F]))
    event.data = data
    return event

def _model_with_backend():
    event = _build_minimal_event()
    root = CommandItem("Root")
    backend = _MockBackend(event)
    model = CommandModel(root, backend=backend, location_id=0)
    model.change_location(0)
    return model

@pytest.fixture
def base_model():
    return _model_with_backend()

@pytest.fixture
def func_index(base_model):
    obj_index = base_model.index(0, 0, QModelIndex())
    return base_model.index(0, 0, obj_index)

def test_empty_model(qtmodeltester, base_model):
    qtmodeltester.check(base_model)

def test_rows_inserted_signal_on_flat_insert(qtbot, base_model, func_index):
    with qtbot.waitSignal(base_model.rowsInserted, timeout=100) as blocker:
        base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    parent_idx, first, last = blocker.args
    assert parent_idx == func_index
    assert first == 0
    assert last == 0

def test_rows_inserted_signal_on_child_insert(qtbot, base_model, func_index):
    if_cmd = EventCommand.if_has_item(1, 0)
    base_model.insert_command(func_index, 0, if_cmd, 32)
    cond_idx = base_model.index(0, 0, func_index)
    
    with qtbot.waitSignal(base_model.rowsInserted, timeout=100) as blocker:
        base_model.insert_command(cond_idx, 0, EventCommand.return_cmd(), 32 + len(if_cmd))
    parent_idx, first, last = blocker.args
    assert parent_idx == cond_idx
    assert first == 0
    assert last == 0

def test_rows_removed_signal_on_delete(qtbot, base_model, func_index):
    base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    with qtbot.waitSignal(base_model.rowsRemoved, timeout=100) as blocker:
        base_model.delete_command(base_model.index(0, 0, func_index))
    parent_idx, first, last = blocker.args
    assert parent_idx == func_index

def test_data_changed_signal_on_update(qtbot, base_model, func_index):
    base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    item = base_model.index(0, 0, func_index).internalPointer()
    with qtbot.waitSignal(base_model.dataChanged, timeout=100):
        base_model.update_command(item, EventCommand.script_speed(3))

def test_data_col0_returns_address_hex(base_model, func_index):
    base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    idx = base_model.index(0, 0, func_index)
    assert base_model.data(idx, Qt.ItemDataRole.DisplayRole) == "0x20"

def test_data_col1_returns_nonempty_command_text(base_model, func_index):
    base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    idx = base_model.index(0, 1, func_index)
    text = base_model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert isinstance(text, str) and len(text) > 0

def test_data_invalid_index_returns_none(base_model):
    assert base_model.data(QModelIndex(), Qt.ItemDataRole.DisplayRole) is None

def test_data_nondisplay_role_returns_none(base_model, func_index):
    base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    idx = base_model.index(0, 0, func_index)
    assert base_model.data(idx, Qt.ItemDataRole.DecorationRole) is None

def test_flags_valid_index(base_model, func_index):
    base_model.insert_command(func_index, 0, EventCommand.script_speed(1), 32)
    idx = base_model.index(0, 0, func_index)
    flags = base_model.flags(idx)
    assert flags & Qt.ItemFlag.ItemIsEnabled
    assert flags & Qt.ItemFlag.ItemIsSelectable

def test_flags_invalid_index(base_model):
    assert base_model.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags

def test_header_data_columns(base_model):
    assert base_model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Address"
    assert base_model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Command"
