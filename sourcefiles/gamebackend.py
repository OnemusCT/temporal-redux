from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

from sourcefiles.jetsoftime import ctevent
from sourcefiles.jetsoftime.ctrom import CTRom
from sourcefiles.jetsoftime.base import basepatch


class GameBackend(ABC):
    """Abstract interface for a game data backend (SNES ROM or PC data files)."""

    @abstractmethod
    def get_script(self, location_id: int) -> ctevent.Event:
        pass

    @abstractmethod
    def get_location_list(self) -> list[tuple[int, str]]:
        pass

    @abstractmethod
    def write_script(self, location_id: int) -> None:
        pass

    @abstractmethod
    def save_to_file(self, path: Path) -> None:
        pass

    @property
    @abstractmethod
    def platform(self) -> str:
        pass

    @property
    @abstractmethod
    def is_read_only(self) -> bool:
        pass


class SnesBackend(GameBackend):
    def __init__(self, ct_rom: CTRom):
        self._ct_rom = ct_rom

    @classmethod
    def from_path(cls, rom_path: Path, ignore_checksum: bool = True) -> SnesBackend:
        rom = CTRom(rom_path.read_bytes(), ignore_checksum)
        basepatch.mark_initial_free_space(rom)
        return cls(rom)

    def get_script(self, location_id: int) -> ctevent.Event:
        return self._ct_rom.script_manager.get_script(location_id)

    def get_location_list(self) -> list[tuple[int, str]]:
        from editorui.lookups import locations as snes_locations
        return list(snes_locations)

    def write_script(self, location_id: int) -> None:
        self._ct_rom.script_manager.write_script_to_rom(location_id)

    def save_to_file(self, path: Path) -> None:
        path.write_bytes(self._ct_rom.rom_data.getvalue())

    @property
    def platform(self) -> str:
        return 'snes'

    @property
    def is_read_only(self) -> bool:
        return False

    @property
    def ct_rom(self) -> CTRom:
        return self._ct_rom
