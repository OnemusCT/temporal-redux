"""Shared Save/Discard/Cancel prompt for leaving a location with unsaved
edits. Used by both the practice save-state editor and the primary event
editor so the wording and button behavior stay identical between them."""
from __future__ import annotations

from enum import Enum, auto

from PyQt6.QtWidgets import QMessageBox, QWidget


class UnsavedChangesChoice(Enum):
    SAVE = auto()
    DISCARD = auto()
    CANCEL = auto()


def prompt_unsaved_changes(parent: QWidget, location_name: str) -> UnsavedChangesChoice:
    """Ask whether to save, discard, or cancel leaving `location_name`, which
    has unsaved edits. Save is the default (safest) button."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Unsaved Changes")
    box.setText(f'"{location_name}" has unsaved changes.')
    box.setInformativeText("Save them before switching locations?")
    box.setStandardButtons(
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel
    )
    box.setDefaultButton(QMessageBox.StandardButton.Save)
    result = box.exec()

    if result == QMessageBox.StandardButton.Save:
        return UnsavedChangesChoice.SAVE
    if result == QMessageBox.StandardButton.Discard:
        return UnsavedChangesChoice.DISCARD
    return UnsavedChangesChoice.CANCEL
