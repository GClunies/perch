import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="perch",
        description="A vantage point for agentic workflows",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Path to the worktree to browse (default: current directory)",
    )
    parser.add_argument(
        "--editor",
        default=None,
        help="Editor command to use for opening files (default: $EDITOR or cursor)",
    )
    args = parser.parse_args()

    resolved = args.path.resolve()

    from perch.services.git import get_worktree_root

    try:
        get_worktree_root(resolved)
    except RuntimeError:
        print(
            f"Error: {resolved} is not a Git repository.\n"
            "Run `git init` first, then run `perch`.",
            file=sys.stderr,
        )
        sys.exit(1)

    from perch.app import PerchApp

    app = PerchApp(worktree_path=resolved, editor=args.editor)
    app.run()
