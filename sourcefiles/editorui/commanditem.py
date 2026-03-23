from __future__ import annotations

from jetsoftime.eventcommand import EventCommand
import editorui.commandtotext as c2t
import jetsoftime.ctevent


class CommandItem:
    def __init__(self, name, command: EventCommand = None, address: int = None, children: list[CommandItem] | None = None):
        self.name = name
        self.command = command
        self.address = address
        self.children = children if children is not None else []
        self.parent = None
        self.is_link: bool = False
        self.is_section_label: bool = False
        self.link_target: tuple[int, int] | None = None  # (obj_id, func_id)

    def add_child(self, child: CommandItem):
        child.parent = self
        self.children.append(child)

    def get_child(self, index: int) -> CommandItem:
        if index < len(self.children):
            return self.children[index]
        return None

    def add_children(self, children: list[CommandItem]):
        for c in children:
            c.parent = self
            self.children.append(c)

    @property
    def row(self) -> int:
        """Get the row number of this item within its parent's children."""
        if self.parent:
            return self.parent.children.index(self)
        return 0
    
def process_script(script: ctevent.Event) -> list[CommandItem]:
    """Process the script into command items"""
    result = []
    for i in range(script.num_objects):
        object_item = CommandItem(f"Object {i:02X}")

        for num, function in enumerate(script.get_all_fuctions(i)):
            is_empty = script._function_is_empty(i, num)
            is_linked = script._function_is_linked(i, num)

            if is_empty or is_linked:
                target = script.get_link_target(i, num)
                # Hide unresolvable arbitrary slots to reduce noise
                if target is None and num >= 3:
                    continue
                func_name = _get_function_name(num)
                if target is not None:
                    tgt_obj, tgt_func = target
                    display_name = (f"{func_name} \u2192 Link to "
                                    f"Obj {tgt_obj:02X} {_get_function_name(tgt_func)}")
                else:
                    display_name = f"{func_name} \u2192 Link (unresolved)"
                func_item = CommandItem(display_name)
                func_item.func_id = num
                func_item.is_link = True
                func_item.link_target = target
                func_item.parent = object_item
                object_item.add_child(func_item)
                continue

            func_start = script.get_function_start(i, num)
            func_name = _get_function_name(num)
            func_item = CommandItem(func_name)
            func_item.func_id = num

            # Build string lookup from the actual commands in this function.
            # Using get_obj_strings would miss strings in commands that fall
            # outside the object's byte range (get_function_end can reach past
            # get_object_end), causing false "ERROR" display for textboxes.
            func_strings = {
                cmd.args[0]: bytearray(script.strings[cmd.args[0]])
                for cmd in function.commands
                if cmd.command in EventCommand.str_commands
                and cmd.args[0] < len(script.strings)
            }

            children, _ = _create_command_list(function.commands, func_strings, func_start)

            if num == 0:
                for idx, child in enumerate(children):
                    if child.command is not None and child.command.command == 0x00:
                        if idx + 1 < len(children):
                            sep = CommandItem("─── Idle ───")
                            sep.is_section_label = True
                            children.insert(idx + 1, sep)
                        break

            for child in children:
                child.parent = func_item
            func_item.add_children(children)

            func_item.parent = object_item
            object_item.add_child(func_item)

        result.append(object_item)
    return result

def _get_function_name(num: int) -> str:
    """Get the function name based on its number"""
    if num == 0:
        return "Startup / Idle"
    elif num == 1:
        return "Activate" 
    elif num == 2:
        return "Touch"
    else:
        func_id = num - 3
        return f"Function {func_id:02X}"
    
def _create_command_list(commands, strings, bytes=0):
    items = []
    i = 0
    curr_bytes = bytes
    while i < len(commands):
        command_str = c2t.command_to_text(commands[i], curr_bytes, strings)
        command_bytes = len(commands[i])
        item = CommandItem(command_str, commands[i], curr_bytes)
        if commands[i].command in EventCommand.conditional_commands and commands[i].num_args > 0:
            bytes_to_jump = commands[i].args[commands[i].num_args-1]
            if bytes_to_jump <= 0:
                items.append(item)
                curr_bytes += command_bytes
                i += 1
                continue
            start = i+1
            while bytes_to_jump > 0:
                i+=1
                if i >= len(commands):
                    break
                bytes_to_jump -= len(commands[i])
            if bytes_to_jump == 0:
                end = i + 1  # loop hit exact boundary; last command is a child
            else:
                end = i      # loop overshot; last command is not a child
                i -= 1
            (child_items, skipped_bytes) = _create_command_list(commands[start:end], strings, curr_bytes+command_bytes)
            item.add_children(child_items)
            curr_bytes += skipped_bytes
        items.append(item)
        curr_bytes += command_bytes
        i+=1

    return (items, curr_bytes-bytes)