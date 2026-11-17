"""Command-line entry point: `hwp-edit-mcp [--read-only] [--root DIR ...] [--rhwp-path EXE]`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from hwp_edit_mcp import __version__
from hwp_edit_mcp.rhwp_backend import RhwpBackend
from hwp_edit_mcp.rhwp_install import ensure_rhwp
from hwp_edit_mcp.server import DEFAULT_MAX_CHARS, create_server, run_stdio_server


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _env_roots() -> list[str]:
    raw = os.environ.get("HWP_EDIT_ROOTS", "")
    # Windows drive letters contain ':', so only split on ':' outside Windows.
    sep = ";" if os.name == "nt" else os.pathsep
    return [r.strip() for r in raw.split(sep) if r.strip()]


def _setup_logging() -> None:
    # stdout carries JSON-RPC, so logs go to stderr (and optionally a file) only.
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    log_file = os.environ.get("HWP_EDIT_LOG_FILE")
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hwp-edit-mcp", description="Safe HWP/HWPX editing MCP server (rhwp).")
    parser.add_argument("--version", action="version", version=f"hwp-edit-mcp {__version__}")
    parser.add_argument("--read-only", action="store_true", help="쓰기 도구를 등록하지 않음 (env HWP_EDIT_READ_ONLY=1)")
    parser.add_argument("--root", action="append", default=None, metavar="DIR", help="허용 폴더, 여러 번 지정 가능 (env HWP_EDIT_ROOTS)")
    parser.add_argument("--rhwp-path", default=None, metavar="EXE", help="rhwp 실행 파일 경로 (env RHWP_EXE)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("install-rhwp", help="rhwp 를 미리 내려받아 캐시에 둠")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    _setup_logging()

    if args.command == "install-rhwp":
        print(ensure_rhwp(args.rhwp_path, allow_download=True))
        return

    max_chars = int(os.environ.get("HWP_EDIT_MAX_CHARS", DEFAULT_MAX_CHARS))
    mcp, rhwp, _ = create_server(
        RhwpBackend(args.rhwp_path),
        read_only=args.read_only or _env_flag("HWP_EDIT_READ_ONLY"),
        roots=args.root or _env_roots(),
        max_chars=max_chars,
    )
    asyncio.run(run_stdio_server(mcp, rhwp))


if __name__ == "__main__":
    main()
