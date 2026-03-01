from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit


class BaseCommandMenu:
    """Base class for command menus with error handling."""

    def __init__(self):
        pass

    def validate(self):
        """Validate all inputs. Returns True if valid, False if not."""
        return True  # Override in subclasses

    def apply_string(self, string_text: str) -> None:
        """Called with the decoded string content when a textbox command is selected."""
        pass

    def get_modified_string(self) -> str | None:
        """Return new string text if the user changed it, else None."""
        return None

    def safe_get_command(self):
        """Get the command, handling any errors."""
        try:
            if not self.validate():
                return None
            return self.get_command()
        except CommandError as e:
            # Find all ValidatingLineEdit widgets and set their tooltips
            widget = self.command_widget()
            error_shown = False
            for child in widget.findChildren(ValidatingLineEdit):
                if child.get_value() is None:
                    child.set_error(str(e))
                    error_shown = True
            # If no specific field was invalid, set tooltip on first input
            if not error_shown:
                first_input = widget.findChild(ValidatingLineEdit)
                if first_input:
                    first_input.set_error(str(e))
            return None
        except Exception as e:
            # Handle unexpected errors similarly
            first_input = self.command_widget().findChild(ValidatingLineEdit)
            if first_input:
                first_input.set_error(f"Unexpected error: {str(e)}")
            return None