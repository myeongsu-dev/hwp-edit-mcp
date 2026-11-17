"""Tests for path resolution and root directory enforcement in create_server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hwp_edit_mcp.server import create_server


class PathTestBackend:
    def __init__(self) -> None:
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    async def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "hwp_export_markdown",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "output": {"type": "string"}},
                },
            }
        ]

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        args = dict(arguments or {})
        self.calls.append((name, args))
        return {"ok": True, "path": args.get("path"), "output": args.get("output")}

    async def run_cli(self, args: List[str], timeout: Optional[float] = None) -> Dict[str, Any]:
        return {"ok": True, "args": args}

    async def close(self) -> None:
        return None


def test_relative_path_uses_first_root(tmp_path: Path):
    root1 = tmp_path / "root1"
    root2 = tmp_path / "root2"
    root1.mkdir()
    root2.mkdir()
    doc = root1 / "sub" / "doc.hwp"
    doc.parent.mkdir()
    doc.write_bytes(b"hwp")

    mcp, _, _ = create_server(backend=PathTestBackend(), roots=[str(root1), str(root2)])

    async def _run():
        res = await mcp.call_tool("hwp_info", {"file_path": "sub/doc.hwp"})
        return json.loads(res[0].text)

    data = asyncio.run(_run())
    assert Path(data["file_path"]) == doc.resolve()


def test_path_outside_roots_rejected(tmp_path: Path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    doc_in = allowed / "in.hwp"
    doc_in.write_bytes(b"in")
    doc_out = outside / "out.hwp"
    doc_out.write_bytes(b"out")

    mcp, _, _ = create_server(backend=PathTestBackend(), roots=[str(allowed)])

    async def _run():
        with pytest.raises(Exception, match="허용 폴더"):
            await mcp.call_tool("hwp_info", {"file_path": str(doc_out)})

        with pytest.raises(Exception, match="허용 폴더"):
            await mcp.call_tool(
                "hwp_render_page",
                {"file_path": str(doc_in), "output_dir": str(outside / "render")},
            )

        with pytest.raises(Exception, match="허용 폴더"):
            await mcp.call_tool(
                "hwp_rhwp_call",
                {
                    "file_path": str(doc_in),
                    "tool_name": "hwp_export_markdown",
                    "arguments": {"output": str(outside / "md")},
                },
            )

    asyncio.run(_run())


def test_relative_path_uses_cwd_when_no_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    doc = tmp_path / "cwd_doc.hwp"
    doc.write_bytes(b"cwd")

    mcp, _, _ = create_server(backend=PathTestBackend(), roots=())

    async def _run():
        res = await mcp.call_tool("hwp_info", {"file_path": "cwd_doc.hwp"})
        return json.loads(res[0].text)

    data = asyncio.run(_run())
    assert Path(data["file_path"]) == doc.resolve()
