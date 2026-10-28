"""
Level 3: Atomic Actions for Mod Toggle (Enable/Disable).
Handles atomic file renaming (.disabled extension) for non-destructive toggling.
"""

from pathlib import Path
from typing import List, Tuple


class ModToggleActions:
    """Atomic actions for toggling mod files on disk."""

    def toggle_file(self, file_path: Path, new_state: bool, mods_dir: Path) -> Tuple[Path, str]:
        """
        Atomically renames a file to append or remove .disabled extension.
        Returns (updated_file_path, relative_path_str).
        """
        rel_path = file_path.relative_to(mods_dir)
        if not new_state:
            # Disable: append .disabled
            if file_path.suffix.lower() in [".package", ".ts4script"]:
                new_file_path = file_path.with_name(file_path.name + ".disabled")
                file_path.replace(new_file_path)
                return new_file_path, str(new_file_path.relative_to(mods_dir))
            return file_path, str(rel_path)
        else:
            # Enable: remove .disabled
            if file_path.name.lower().endswith(".package.disabled") or file_path.name.lower().endswith(
                ".ts4script.disabled"
            ):
                new_file_path = file_path.with_name(file_path.name[:-9])
                file_path.replace(new_file_path)
                return new_file_path, str(new_file_path.relative_to(mods_dir))
            return file_path, str(rel_path)

    def toggle_folder_files(self, mod_folder: Path, new_state: bool, mods_dir: Path) -> List[str]:
        """Traverses mod folder and applies atomic toggle renaming to all mod files."""
        updated_files: List[str] = []
        for file_path in mod_folder.rglob("*"):
            if not file_path.is_file():
                continue
            _, rel_str = self.toggle_file(file_path, new_state, mods_dir)
            updated_files.append(rel_str)
        return updated_files

    def toggle_target(self, mod_target: Path, new_state: bool, mods_dir: Path) -> List[str]:
        """Atomically toggles a mod folder or a single loose mod file."""
        if mod_target.is_file():
            _, rel_str = self.toggle_file(mod_target, new_state, mods_dir)
            return [rel_str]
        return self.toggle_folder_files(mod_target, new_state, mods_dir)
