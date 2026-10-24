"""Draft folder manager."""

import os
import shutil

from typing import List

from .script_file import Script_file

class Draft_folder:
    """Manages a folder and the drafts inside it."""

    folder_path: str
    """Root path."""

    def __init__(self, folder_path: str):
        """Initialise the draft folder manager.

        Args:
            folder_path (`str`): a folder containing drafts, normally the editor's own drafts location

        Raises:
            `FileNotFoundError`: the path does not exist
        """
        self.folder_path = folder_path

        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Root folder {self.folder_path} does not exist")

    def list_drafts(self) -> List[str]:
        """List the names of every draft in the folder.

        Note: this simply lists the subfolder names; it does not check that they are valid drafts.
        """
        return [f for f in os.listdir(self.folder_path) if os.path.isdir(os.path.join(self.folder_path, f))]

    def remove(self, draft_name: str) -> None:
        """Delete the named draft.

        Args:
            draft_name (`str`): the draft name, i.e. its folder name

        Raises:
            `FileNotFoundError`: that draft does not exist
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if not os.path.exists(draft_path):
            raise FileNotFoundError(f"Draft folder {draft_name} does not exist")

        shutil.rmtree(draft_path)

    def inspect_material(self, draft_name: str) -> None:
        """Print the sticker material metadata in the named draft.

        Args:
            draft_name (`str`): the draft name, i.e. its folder name

        Raises:
            `FileNotFoundError`: that draft does not exist
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if not os.path.exists(draft_path):
            raise FileNotFoundError(f"Draft folder {draft_name} does not exist")

        script_file = self.load_template(draft_name)
        script_file.inspect_material()

    def load_template(self, draft_name: str) -> Script_file:
        """Open a draft in the folder as a template and edit it in place.

        Args:
            draft_name (`str`): the draft name, i.e. its folder name

        Returns:
            `Script_file`: the draft, opened in template mode

        Raises:
            `FileNotFoundError`: that draft does not exist
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if not os.path.exists(draft_path):
            raise FileNotFoundError(f"Draft folder {draft_name} does not exist")

        return Script_file.load_template(os.path.join(draft_path, "draft_info.json"))

    def duplicate_as_template(self, template_name: str, new_draft_name: str, allow_replace: bool = False) -> Script_file:
        """Copy a draft and edit the copy.

        Args:
            template_name (`str`): the source draft name
            new_draft_name (`str`): the new draft name
            allow_replace (`bool`, optional): whether an existing draft named `new_draft_name` may be overwritten. Defaults to False.

        Returns:
            `Script_file`: the **copied** draft, opened in template mode

        Raises:
            `FileNotFoundError`: the source draft does not exist
            `FileExistsError`: a draft named `new_draft_name` already exists and overwriting is not allowed.
        """
        template_path = os.path.join(self.folder_path, template_name)
        new_draft_path = os.path.join(self.folder_path, new_draft_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template draft {template_name} does not exist")
        if os.path.exists(new_draft_path) and not allow_replace:
            raise FileExistsError(f"Draft {new_draft_name} already exists and overwriting is not allowed")

        # Copy the draft folder
        shutil.copytree(template_path, new_draft_path, dirs_exist_ok=allow_replace)

        # Open the draft
        return self.load_template(new_draft_name)
