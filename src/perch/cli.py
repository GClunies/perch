import argparse
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

    from perch.app import PerchApp

    app = PerchApp(worktree_path=args.path.resolve(), editor=args.editor)
    app.run(mouse=False)
