"""Diff engine for comparing event scripts between two backends."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from editorui.commanditem import CommandItem, process_script, _get_function_name
from jetsoftime.ctevent import Event
from jetsoftime.eventcommand import EventCommand, Platform, PC_ONLY_OPCODES, CROSS_PLATFORM_INCOMPATIBLE_OPCODES


class DiffStatus(Enum):
    """Status of a single diff line."""
    EQUAL = auto()
    MODIFIED = auto()
    LEFT_ONLY = auto()
    RIGHT_ONLY = auto()


class CopyEligibility(Enum):
    """Whether a diff line's command can be copied to the other side."""
    ALLOWED = auto()
    BLOCKED_PC_ONLY = auto()
    BLOCKED_CROSS_PLATFORM = auto()
    BLOCKED_READ_ONLY = auto()


def get_copy_eligibility(
    command: EventCommand,
    source_platform: Platform,
    target_platform: Platform,
    target_read_only: bool,
) -> CopyEligibility:
    """Determine whether a command can be copied from source to target.

    Returns the most specific blocking reason, or ALLOWED.
    """
    if target_read_only:
        return CopyEligibility.BLOCKED_READ_ONLY
    if source_platform == target_platform:
        return CopyEligibility.ALLOWED
    # Cross-platform copy
    if command.command in PC_ONLY_OPCODES:
        return CopyEligibility.BLOCKED_PC_ONLY
    if command.command in CROSS_PLATFORM_INCOMPATIBLE_OPCODES:
        return CopyEligibility.BLOCKED_CROSS_PLATFORM
    return CopyEligibility.ALLOWED


@dataclass
class DiffLine:
    """A single aligned pair of commands in the diff."""
    left: Optional[EventCommand]
    right: Optional[EventCommand]
    status: DiffStatus
    left_address: Optional[int] = None
    right_address: Optional[int] = None
    left_name: str = ""
    right_name: str = ""
    copy_left_to_right: CopyEligibility = CopyEligibility.ALLOWED
    copy_right_to_left: CopyEligibility = CopyEligibility.ALLOWED


@dataclass
class FunctionDiff:
    """Diff result for a single object function."""
    object_index: int
    function_index: int
    function_name: str
    lines: list[DiffLine] = field(default_factory=list)

    @property
    def is_identical(self) -> bool:
        return all(line.status == DiffStatus.EQUAL for line in self.lines)


@dataclass
class LocationDiff:
    """Diff result for an entire location's event script."""
    location_id: int
    functions: list[FunctionDiff] = field(default_factory=list)
    left_num_objects: int = 0
    right_num_objects: int = 0

    @property
    def is_identical(self) -> bool:
        return all(f.is_identical for f in self.functions)


def _command_signature(cmd: EventCommand) -> tuple:
    """Create a hashable signature for a command (opcode + args)."""
    args = tuple(
        bytes(a) if isinstance(a, (bytearray, bytes)) else a
        for a in cmd.args
    )
    return (cmd.command, args)


def _flatten_commands(item: CommandItem) -> list[tuple[EventCommand, int, str]]:
    """Recursively flatten a CommandItem tree into (command, address, name) tuples.

    This flattens the conditional nesting so the diff operates on a flat
    sequence of commands in script order.
    """
    # TODO - figure out how to do this without flattening so it's easier to read diffs
    result = []
    for child in item.children:
        if child.command is not None:
            result.append((child.command, child.address, child.name))
        # Recurse into children (conditionals nest their body commands)
        result.extend(_flatten_commands(child))
    return result


def _diff_command_lists(
    left_cmds: list[tuple[EventCommand, int, str]],
    right_cmds: list[tuple[EventCommand, int, str]],
) -> list[DiffLine]:
    """Diff two flat command lists using SequenceMatcher."""
    left_sigs = [_command_signature(cmd) for cmd, _, _ in left_cmds]
    right_sigs = [_command_signature(cmd) for cmd, _, _ in right_cmds]

    matcher = difflib.SequenceMatcher(None, left_sigs, right_sigs)
    lines: list[DiffLine] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                l_cmd, l_addr, l_name = left_cmds[i]
                r_cmd, r_addr, r_name = right_cmds[j]
                lines.append(DiffLine(
                    left=l_cmd, right=r_cmd,
                    status=DiffStatus.EQUAL,
                    left_address=l_addr, right_address=r_addr,
                    left_name=l_name, right_name=r_name,
                ))
        elif tag == "replace":
            # Match up replaced elements one-to-one to keep them visually adjacent.
            # If one side has more elements than the other, treat the remainder
            # as simple insertions/deletions.
            left_slice = list(range(i1, i2))
            right_slice = list(range(j1, j2))
            paired = min(len(left_slice), len(right_slice))
            for k in range(paired):
                l_cmd, l_addr, l_name = left_cmds[left_slice[k]]
                r_cmd, r_addr, r_name = right_cmds[right_slice[k]]
                lines.append(DiffLine(
                    left=l_cmd, right=r_cmd,
                    status=DiffStatus.MODIFIED,
                    left_address=l_addr, right_address=r_addr,
                    left_name=l_name, right_name=r_name,
                ))
            # Remaining left-only
            for k in range(paired, len(left_slice)):
                l_cmd, l_addr, l_name = left_cmds[left_slice[k]]
                lines.append(DiffLine(
                    left=l_cmd, right=None,
                    status=DiffStatus.LEFT_ONLY,
                    left_address=l_addr, left_name=l_name,
                ))
            # Remaining right-only
            for k in range(paired, len(right_slice)):
                r_cmd, r_addr, r_name = right_cmds[right_slice[k]]
                lines.append(DiffLine(
                    left=None, right=r_cmd,
                    status=DiffStatus.RIGHT_ONLY,
                    right_address=r_addr, right_name=r_name,
                ))
        elif tag == "delete":
            for i in range(i1, i2):
                l_cmd, l_addr, l_name = left_cmds[i]
                lines.append(DiffLine(
                    left=l_cmd, right=None,
                    status=DiffStatus.LEFT_ONLY,
                    left_address=l_addr, left_name=l_name,
                ))
        elif tag == "insert":
            for j in range(j1, j2):
                r_cmd, r_addr, r_name = right_cmds[j]
                lines.append(DiffLine(
                    left=None, right=r_cmd,
                    status=DiffStatus.RIGHT_ONLY,
                    right_address=r_addr, right_name=r_name,
                ))

    return lines


def _apply_copy_eligibility(
    lines: list[DiffLine],
    left_platform: Platform,
    right_platform: Platform,
    left_read_only: bool,
    right_read_only: bool,
) -> None:
    """Set copy_left_to_right and copy_right_to_left on each DiffLine."""
    for line in lines:
        if line.left is not None:
            line.copy_left_to_right = get_copy_eligibility(
                line.left, left_platform, right_platform, right_read_only,
            )
        else:
            line.copy_left_to_right = CopyEligibility.ALLOWED

        if line.right is not None:
            line.copy_right_to_left = get_copy_eligibility(
                line.right, right_platform, left_platform, left_read_only,
            )
        else:
            line.copy_right_to_left = CopyEligibility.ALLOWED


def _extract_object_functions(
    items: list[CommandItem], obj_idx: int
) -> dict[int, CommandItem]:
    """Extract a mapping of function IDs to CommandItems for a given object."""
    funcs: dict[int, CommandItem] = {}
    obj = items[obj_idx] if obj_idx < len(items) else None
    if obj is not None:
        for func_item in obj.children:
            func_id = getattr(func_item, "func_id", None)
            if func_id is not None:
                funcs[func_id] = func_item
    return funcs


def eligibility_reason(eligibility: CopyEligibility) -> str:
    """Human-readable explanation for a blocked copy."""
    if eligibility == CopyEligibility.BLOCKED_PC_ONLY:
        return "PC-only opcode cannot be copied to SNES"
    if eligibility == CopyEligibility.BLOCKED_CROSS_PLATFORM:
        return "Cross-platform argument encoding differs"
    if eligibility == CopyEligibility.BLOCKED_READ_ONLY:
        return "Target is read-only"
    return ""


def compute_location_identical(
    left_event: Event,
    right_event: Event,
) -> bool:
    """Fast check: are two Events' scripts identical command-by-command?

    Cheaper than compute_location_diff \u2014 builds no DiffLine objects and
    short-circuits on the first mismatch.
    """
    left_items = process_script(left_event)
    right_items = process_script(right_event)

    if left_event.num_objects != right_event.num_objects:
        return False

    for obj_idx in range(left_event.num_objects):
        left_funcs = _extract_object_functions(left_items, obj_idx)
        right_funcs = _extract_object_functions(right_items, obj_idx)

        if set(left_funcs.keys()) != set(right_funcs.keys()):
            return False

        for func_id in left_funcs:
            left_cmds = _flatten_commands(left_funcs[func_id])
            right_cmds = _flatten_commands(right_funcs[func_id])

            if len(left_cmds) != len(right_cmds):
                return False
            for (l_cmd, _, _), (r_cmd, _, _) in zip(left_cmds, right_cmds):
                if _command_signature(l_cmd) != _command_signature(r_cmd):
                    return False

    return True


def compute_location_diff(
    left_event: Event,
    right_event: Event,
    location_id: int,
    left_read_only: bool = False,
    right_read_only: bool = False,
) -> LocationDiff:
    """Compute a command-level diff between two Events for the same location.

    Each object's 16 function slots are compared independently. Objects that
    exist only on one side produce entirely one-sided diff lines.

    Copy eligibility is computed from each Event's platform and the read-only
    flags of the backends.
    """
    left_items = process_script(left_event)
    right_items = process_script(right_event)

    max_objects = max(left_event.num_objects, right_event.num_objects)
    functions: list[FunctionDiff] = []

    for obj_idx in range(max_objects):
        left_funcs = _extract_object_functions(left_items, obj_idx)
        right_funcs = _extract_object_functions(right_items, obj_idx)

        all_func_ids = sorted(set(left_funcs.keys()) | set(right_funcs.keys()))

        for func_id in all_func_ids:
            left_func = left_funcs.get(func_id)
            right_func = right_funcs.get(func_id)

            left_cmds = _flatten_commands(left_func) if left_func else []
            right_cmds = _flatten_commands(right_func) if right_func else []

            # Skip functions empty on both sides
            if not left_cmds and not right_cmds:
                continue

            diff_lines = _diff_command_lists(left_cmds, right_cmds)
            _apply_copy_eligibility(
                diff_lines,
                left_event.platform, right_event.platform,
                left_read_only, right_read_only,
            )

            func_diff = FunctionDiff(
                object_index=obj_idx,
                function_index=func_id,
                function_name=_get_function_name(func_id),
                lines=diff_lines,
            )
            functions.append(func_diff)

    return LocationDiff(
        location_id=location_id,
        functions=functions,
        left_num_objects=left_event.num_objects,
        right_num_objects=right_event.num_objects,
    )
