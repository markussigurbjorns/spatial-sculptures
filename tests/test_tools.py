"""Check location-independent launch arguments and actual subprocess status propagation."""

import contextlib
import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.run_blender import REPOSITORY_ROOT, build_command, prototype_script, run


class ToolTests(unittest.TestCase):
    def test_package_and_prototype_imports_without_blender(self) -> None:
        import sys

        for base in (REPOSITORY_ROOT / "src" / "spatial_sculptures", REPOSITORY_ROOT / "tools"):
            for path in base.rglob("*.py"):
                root = (
                    REPOSITORY_ROOT / "src"
                    if "src" in path.relative_to(REPOSITORY_ROOT).parts
                    else REPOSITORY_ROOT
                )
                parts = list(path.relative_to(root).with_suffix("").parts)
                if parts[-1] == "__init__":
                    parts.pop()
                importlib.import_module(".".join(parts))
        prototype = REPOSITORY_ROOT / "prototypes" / "001_resonant_surface"
        for path in prototype.rglob("*.py"):
            importlib.import_module(
                ".".join(path.relative_to(REPOSITORY_ROOT).with_suffix("").parts)
            )
        self.assertNotIn("bpy", sys.modules)

    def test_paths_and_blender_argument_order(self) -> None:
        with patch.dict(os.environ, {"BLENDER_BIN": "/a path/blender"}):
            command = build_command("001_resonant_surface", background=True, frame=97)
        self.assertEqual(command[0], "/a path/blender")
        self.assertLess(command.index("--background"), command.index("--python"))
        self.assertLess(command.index("--python-exit-code"), command.index("--python"))
        self.assertTrue(Path(command[command.index("--python") + 1]).is_absolute())
        self.assertEqual(command[command.index("--") + 1 :], ["--frame", "97"])

    def test_path_traversal_and_missing_prototypes(self) -> None:
        for name in ("../tools", "missing", "/tmp"):
            with self.assertRaises(ValueError):
                prototype_script(name)

    @unittest.skipIf(os.name == "nt", "Test executable is a POSIX shell script")
    def test_exit_status_from_executable_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "fake blender"
            executable.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            executable.chmod(0o755)
            with patch.dict(os.environ, {"BLENDER_BIN": str(executable)}):
                self.assertEqual(run("001_resonant_surface", background=True), 7)

    def test_missing_executable_returns_127(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"BLENDER_BIN": str(Path(directory) / "missing")}):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(run("001_resonant_surface"), 127)


if __name__ == "__main__":
    unittest.main()
