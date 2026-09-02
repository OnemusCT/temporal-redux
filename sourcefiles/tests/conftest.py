import sys

from pathlib import Path

# The project is imported under two different roots: gamebackend.py reaches
# its siblings via "sourcefiles.jetsoftime.x", while editorui/ and practice/
# import "jetsoftime.x" unqualified, as if sourcefiles/ were a path root.
# Both styles coexist today (see practice/apply_dumps.py's note on it), so a
# test run has to satisfy both regardless of which directory it starts from.
_SOURCEFILES_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT_DIR = _SOURCEFILES_DIR.parent
for _path_entry in (str(_SOURCEFILES_DIR), str(_REPO_ROOT_DIR)):
    if _path_entry not in sys.path:
        sys.path.append(_path_entry)
