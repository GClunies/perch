import subprocess
from pathlib import Path

from perch.widgets.file_tree import ALWAYS_EXCLUDED, FileTree


def _init_git_repo_with_commit(path: Path) -> None:
    """Create a git repo with an initial commit so PerchApp can resolve a branch."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(path),
        },
    )


def _init_git_repo(path: Path, gitignore: str = "") -> None:
    """Create a git repo with an optional .gitignore."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    if gitignore:
        (path / ".gitignore").write_text(gitignore)


class TestFilterPaths:
    """Tests for FileTree.filter_paths()."""

    def test_always_excludes_git_directory(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / ".git", tmp_path / "src"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert ".git" in ALWAYS_EXCLUDED
        assert ".git" not in result
        assert "src" in result

    def test_shows_gitignored_files(self, tmp_path: Path) -> None:
        """Gitignored files should appear but be tracked as ignored."""
        _init_git_repo(tmp_path, gitignore="__pycache__/\n.venv/\n")
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / "__pycache__", tmp_path / ".venv", tmp_path / "src"]
        result = [p.name for p in tree.filter_paths(paths)]
        # All shown — nothing filtered out (except .git)
        assert "__pycache__" in result
        assert ".venv" in result
        assert "src" in result
        # But ignored paths are tracked
        assert tmp_path / "__pycache__" in tree._ignored_paths
        assert tmp_path / ".venv" in tree._ignored_paths
        assert tmp_path / "src" not in tree._ignored_paths

    def test_keeps_normal_files(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / "src", tmp_path / "tests", tmp_path / "pyproject.toml"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert result == ["src", "tests", "pyproject.toml"]

    def test_empty_input(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert list(tree.filter_paths([])) == []

    def test_graceful_without_git_repo(self, tmp_path: Path) -> None:
        """Without a git repo, all files except .git are shown."""
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / ".git", tmp_path / "src", tmp_path / "__pycache__"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert ".git" not in result
        assert "src" in result
        assert "__pycache__" in result


class TestIsDimmed:
    """Tests for _is_dimmed() — dotfiles and gitignored paths."""

    def test_dotfile_is_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / ".env") is True

    def test_dotdir_is_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / ".venv") is True

    def test_normal_file_not_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / "main.py") is False

    def test_ignored_path_is_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        tree._ignored_paths.add(tmp_path / "node_modules")
        assert tree._is_dimmed(tmp_path / "node_modules") is True

    def test_non_ignored_path_not_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        tree._ignored_paths.add(tmp_path / "dist")
        assert tree._is_dimmed(tmp_path / "src") is False


class TestRootNodeProtection:
    """The root node must never be collapsible."""

    async def test_action_collapse_node_does_not_collapse_root(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp

        _init_git_repo_with_commit(tmp_path)
        with (
            patch("perch.services.git.get_status", return_value=__import__("perch.models", fromlist=["GitStatusData"]).GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                await pilot.pause()
                # Ensure root is expanded
                assert tree.root.is_expanded
                # Position cursor on root
                tree.cursor_line = 0
                tree.action_collapse_node()
                await pilot.pause()
                assert tree.root.is_expanded, "Root should never be collapsed"

    async def test_on_tree_node_collapsed_reexpands_root(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp

        _init_git_repo_with_commit(tmp_path)
        with (
            patch("perch.services.git.get_status", return_value=__import__("perch.models", fromlist=["GitStatusData"]).GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                await pilot.pause()
                assert tree.root.is_expanded
                # Force-collapse root directly (simulates a click on the toggle)
                tree.root.collapse()
                await pilot.pause()
                assert tree.root.is_expanded, "Root should be re-expanded automatically"


class TestActionCopyPath:
    """Tests for FileTree.action_copy_path()."""

    async def test_copy_path_copies_file_path(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "hello.py").write_text("print('hello')\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find a file node
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if node is not None and node.data is not None and not node._allow_expand:
                        break

                with patch.object(pilot.app, "copy_to_clipboard") as mock_copy:
                    tree.action_copy_path()
                    mock_copy.assert_called_once()
                    copied = mock_copy.call_args[0][0]
                    assert "hello.py" in copied

    async def test_copy_path_noop_when_data_not_path(self, tmp_path: Path) -> None:
        """action_copy_path returns early when path is not a Path instance (line 61)."""
        from unittest.mock import patch, PropertyMock, MagicMock

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                await pilot.pause()

                # Fake a node whose data is a non-Path string (no .path attr)
                fake_node = MagicMock()
                fake_node.data = "not-a-path-object"
                del fake_node.path  # ensure hasattr(data, "path") is False
                with (
                    patch.object(type(tree), "cursor_node", new_callable=PropertyMock, return_value=fake_node),
                    patch.object(pilot.app, "copy_to_clipboard") as mock_copy,
                ):
                    tree.action_copy_path()
                    mock_copy.assert_not_called()

    async def test_copy_path_noop_when_no_data(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                await pilot.pause()

                # Patch cursor_node to return a node with data=None
                from unittest.mock import PropertyMock, MagicMock

                fake_node = MagicMock()
                fake_node.data = None
                with (
                    patch.object(type(tree), "cursor_node", new_callable=PropertyMock, return_value=fake_node),
                    patch.object(pilot.app, "copy_to_clipboard") as mock_copy,
                ):
                    tree.action_copy_path()
                    mock_copy.assert_not_called()


class TestActionExpandNode:
    """Tests for FileTree.action_expand_node()."""

    async def test_expand_collapsed_folder(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("x = 1\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find a folder node (expandable, not root)
                folder_node = None
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if node is not None and node._allow_expand and node is not tree.root:
                        folder_node = node
                        break

                assert folder_node is not None, "Expected to find a folder node"

                # Collapse it first if expanded
                if folder_node.is_expanded:
                    folder_node.collapse()
                    await pilot.pause()

                assert not folder_node.is_expanded
                tree.action_expand_node()
                await pilot.pause()
                assert folder_node.is_expanded


class TestActionCollapseNode:
    """Tests for action_collapse_node branches."""

    async def test_collapse_expanded_non_root_folder(self, tmp_path: Path) -> None:
        """Collapsing an expanded non-root folder should collapse it (line 78)."""
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("x = 1\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
            patch("perch.widgets.file_tree.FileTree._watch_filesystem"),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(20):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find the subdir folder node
                folder_node = None
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if (
                        node is not None
                        and node._allow_expand
                        and node is not tree.root
                    ):
                        folder_node = node
                        break

                assert folder_node is not None, "Expected a subfolder"

                # Ensure it's expanded
                if not folder_node.is_expanded:
                    folder_node.expand()
                    for _ in range(20):
                        await pilot.pause()
                        if folder_node.children:
                            break

                assert folder_node.is_expanded

                # Cursor is already on the folder node, call collapse
                # This should hit the first `if` branch (node._allow_expand and is_expanded)
                # and execute node.collapse() on line 78
                collapse_called = False
                original_collapse = folder_node.collapse

                def spy_collapse():
                    nonlocal collapse_called
                    collapse_called = True
                    original_collapse()

                folder_node.collapse = spy_collapse
                tree.action_collapse_node()
                assert collapse_called, "node.collapse() should have been called for expanded non-root folder"

    async def test_collapse_navigates_to_parent_from_file(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("x = 1\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
            patch("perch.widgets.file_tree.FileTree._watch_filesystem"),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(20):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find the subdir folder and expand it
                folder_node = None
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if (
                        node is not None
                        and node._allow_expand
                        and node is not tree.root
                    ):
                        folder_node = node
                        break

                assert folder_node is not None, "Expected a subfolder"

                if not folder_node.is_expanded:
                    folder_node.expand()
                    # Wait for children to load
                    for _ in range(20):
                        await pilot.pause()
                        if folder_node.children:
                            break

                assert folder_node.is_expanded
                assert folder_node.children, "Folder should have children after expand"

                # Find a file child of the folder
                file_node = None
                for child in folder_node.children:
                    if not child._allow_expand:
                        file_node = child
                        break

                assert file_node is not None, "Expected a file inside a subfolder"

                # Position cursor on the file node
                tree.select_node(file_node)
                await pilot.pause()
                assert tree.cursor_node is file_node

                parent = file_node.parent
                # Spy on parent.collapse to verify it was called
                original_collapse = parent.collapse
                collapse_called = False

                def spy_collapse():
                    nonlocal collapse_called
                    collapse_called = True
                    original_collapse()

                parent.collapse = spy_collapse
                tree.action_collapse_node()
                # Verify cursor moved to parent and collapse was invoked
                assert tree.cursor_node is parent
                assert collapse_called, "parent.collapse() should have been called"

    async def test_collapse_from_file_under_root_does_not_collapse_root(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "hello.py").write_text("print('hello')\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find a file node whose parent is root
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if (
                        node is not None
                        and not node._allow_expand
                        and node.parent is tree.root
                    ):
                        break

                assert node is not None and node.parent is tree.root
                tree.action_collapse_node()
                await pilot.pause()
                assert tree.root.is_expanded, "Root should remain expanded"


class TestPageNavigation:
    """Tests for action_page_up and action_page_down."""

    async def test_page_down_moves_cursor(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        # Create enough files so page navigation has room
        for i in range(20):
            (tmp_path / f"file_{i:02d}.py").write_text(f"x = {i}\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                tree.cursor_line = 0
                initial = tree.cursor_line
                tree.action_page_down()
                await pilot.pause()
                assert tree.cursor_line > initial

    async def test_page_up_moves_cursor(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData

        _init_git_repo_with_commit(tmp_path)
        for i in range(20):
            (tmp_path / f"file_{i:02d}.py").write_text(f"x = {i}\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Move down first, then page up
                tree.action_page_down()
                await pilot.pause()
                after_down = tree.cursor_line
                tree.action_page_up()
                await pilot.pause()
                assert tree.cursor_line < after_down


class TestRenderLabel:
    """Tests for render_label edge cases."""

    async def test_render_label_dimmed_path(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData
        from rich.style import Style

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / ".hidden_file").write_text("secret\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find the .hidden_file node
                hidden_node = None
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if node is not None and node.data is not None:
                        data_path = node.data.path if hasattr(node.data, "path") else node.data
                        if isinstance(data_path, Path) and data_path.name == ".hidden_file":
                            hidden_node = node
                            break

                assert hidden_node is not None, "Expected to find .hidden_file node"
                label = tree.render_label(hidden_node, Style(), Style())
                # The label should have "dim" styling applied
                assert label.style == "" or True  # We check the spans
                # Check that some part of the label has dim style
                has_dim = any("dim" in str(span.style) for span in label._spans)
                # Or the whole label was stylized with dim
                assert has_dim or "dim" in str(label.style), f"Expected dim label for .hidden_file, got spans: {label._spans}"

    async def test_render_label_unknown_git_status(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData
        from rich.style import Style

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "tracked.py").write_text("x = 1\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Set an unknown git status for the file
                tree._git_status["tracked.py"] = "X"

                # Find tracked.py node
                target_node = None
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if node is not None and node.data is not None:
                        data_path = node.data.path if hasattr(node.data, "path") else node.data
                        if isinstance(data_path, Path) and data_path.name == "tracked.py":
                            target_node = node
                            break

                assert target_node is not None, "Expected to find tracked.py node"
                label = tree.render_label(target_node, Style(), Style())
                # Should not contain any git indicator since "X" is unknown
                assert " X" not in label.plain

    async def test_render_label_path_outside_tree_root(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData
        from rich.style import Style

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "hello.py").write_text("print('hello')\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find hello.py node
                target_node = None
                for line_idx in range(tree.last_line + 1):
                    tree.cursor_line = line_idx
                    node = tree.cursor_node
                    if node is not None and node.data is not None:
                        data_path = node.data.path if hasattr(node.data, "path") else node.data
                        if isinstance(data_path, Path) and data_path.name == "hello.py":
                            target_node = node
                            break

                assert target_node is not None, "Expected to find hello.py node"

                # Set a git status for the file so it reaches the relative_to call
                tree._git_status["hello.py"] = "modified"

                # Temporarily change tree.path to a completely different directory
                # so path.relative_to(self.path) raises ValueError
                original_path = tree.path
                tree.path = "/nonexistent/other/root"
                label = tree.render_label(target_node, Style(), Style())
                tree.path = original_path

                # Should not crash, should return label without git indicator
                assert label.plain  # label exists and is non-empty

    async def test_render_label_node_data_none(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp
        from perch.models import GitStatusData
        from rich.style import Style

        _init_git_repo_with_commit(tmp_path)
        (tmp_path / "hello.py").write_text("print('hello')\n")

        with (
            patch("perch.services.git.get_status", return_value=GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                for _ in range(10):
                    await pilot.pause()
                    if tree.last_line > 0:
                        break

                # Find any node, then set its data to None
                tree.cursor_line = 0
                node = tree.cursor_node
                assert node is not None

                original_data = node.data
                node.data = None
                label = tree.render_label(node, Style(), Style())
                node.data = original_data

                # Should return label without crash
                assert label.plain  # label exists and is non-empty
