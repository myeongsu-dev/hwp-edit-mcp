"""Tests for tool schemas, annotations, read-only mode, max_chars truncation, and rhwp write detection."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hwp_edit_mcp.server import create_server

SNAPSHOT_PATH = Path(__file__).resolve().parent / "snapshots" / "tools.json"


class FakeBackend:
    """Minimal in-memory RhwpBackend double for schema and server logic tests."""

    def __init__(self) -> None:
        self.calls: List[tuple[str, Dict[str, Any]]] = []
        self.tools: List[Dict[str, Any]] = [
            {
                "name": "hwp_word_count",
                "description": "word count",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
            {
                "name": "hwp_add_bookmark",
                "description": "add bookmark",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "output": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["path", "name"],
                },
            },
            {
                "name": "hwp_export_markdown",
                "description": "export markdown",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "output": {"type": "string"},
                    },
                    "required": ["path", "output"],
                },
            },
        ]

    async def list_tools(self) -> List[Dict[str, Any]]:
        return self.tools

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hwp_info":
            return {"format": "hwp5", "pageCount": 1, "paragraphCount": 2}
        if name == "hwp_export_text":
            return {"text": "A" * 500}
        if name == "hwp_export_tables":
            return {
                "tables": [
                    {"cells": [{"row": 0, "col": 0, "text": "X" * 300}]},
                ]
            }
        if name == "hwp_search":
            return {"matches": [{"text": "Y" * 300}]}
        if name == "hwp_add_bookmark":
            out = args.get("output")
            if out:
                Path(out).write_bytes(Path(args["path"]).read_bytes() + b"-bm")
            return {"ok": True, "losses": []}
        if name == "hwp_run_plan":
            plan = args["plan"]
            Path(plan["output"]).write_bytes(Path(plan["input"]).read_bytes() + b"-plan")
            return {"ok": True, "losses": []}
        return {"ok": True, "tool": name}

    async def run_cli(self, args: List[str], timeout: Optional[float] = None) -> Dict[str, Any]:
        return {"ok": True}

    async def close(self) -> None:
        return None


def _contains_forbidden_keys(obj: Any) -> List[str]:
    found: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("anyOf", "$ref", "$defs"):
                found.append(k)
            found.extend(_contains_forbidden_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_contains_forbidden_keys(item))
    return found


def test_tool_schemas_simplified_annotations_and_snapshot():
    mcp, _, _ = create_server(backend=FakeBackend())
    tools = asyncio.run(mcp.list_tools())
    dumped = [t.model_dump(mode="json") for t in tools]

    assert len(dumped) == 14
    for t in dumped:
        assert t["outputSchema"] is None, f"{t['name']} should not have outputSchema"
        assert t["annotations"] is not None, f"{t['name']} missing annotations"
        assert t["annotations"]["openWorldHint"] is False
        forbidden = _contains_forbidden_keys(t["inputSchema"])
        assert not forbidden, f"{t['name']} has forbidden schema keys: {forbidden}"

    fill_cells = next(t for t in dumped if t["name"] == "hwp_fill_cells")
    cell_props = fill_cells["inputSchema"]["properties"]["cells"]["items"]["properties"]
    for field in ("text", "label", "direction", "occurrence", "row", "col", "table", "keep_style"):
        assert field in cell_props, f"CellInput missing {field}"

    if not SNAPSHOT_PATH.is_file() or os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(
            json.dumps(dumped, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        assert dumped == expected


def test_read_only_mode_tools_and_annotations():
    mcp, _, _ = create_server(backend=FakeBackend(), read_only=True)
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "hwp_info",
        "hwp_get_text",
        "hwp_search",
        "hwp_table_view",
        "hwp_history",
        "hwp_diff",
        "hwp_render_page",
        "hwp_rhwp_call",
    }
    for t in tools:
        assert t.annotations is not None
        assert t.annotations.destructiveHint is not True


def test_explicit_null_optional_argument_accepted(tmp_path: Path):
    doc = tmp_path / "sample.hwp"
    doc.write_bytes(b"dummy-hwp")
    mcp, _, _ = create_server(backend=FakeBackend())

    async def _run():
        res = await mcp.call_tool("hwp_info", {"file_path": str(doc), "password": None})
        return json.loads(res[0].text)

    data = asyncio.run(_run())
    assert data["format"] == "hwp5"


def test_max_chars_truncation_and_override(tmp_path: Path):
    doc = tmp_path / "doc.hwp"
    doc.write_bytes(b"dummy")
    doc_b = tmp_path / "doc_b.hwp"
    doc_b.write_bytes(b"dummy-b")

    class DiffBackend(FakeBackend):
        async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None, timeout=None):
            if name == "hwp_export_text":
                p = (arguments or {}).get("path", "")
                if p.endswith("doc_b.hwp"):
                    return {"text": "\n".join(f"lineB-{i}" for i in range(40))}
                return {"text": "\n".join(f"lineA-{i}" for i in range(40))}
            return await super().call_tool(name, arguments, timeout)

    mcp, _, _ = create_server(backend=DiffBackend(), max_chars=180)

    async def _run():
        r_text = json.loads((await mcp.call_tool("hwp_get_text", {"file_path": str(doc)}))[0].text)
        r_override = json.loads(
            (await mcp.call_tool("hwp_get_text", {"file_path": str(doc), "max_chars": 5000}))[0].text
        )
        r_tbl = json.loads((await mcp.call_tool("hwp_table_view", {"file_path": str(doc)}))[0].text)
        r_search = json.loads(
            (await mcp.call_tool("hwp_search", {"file_path": str(doc), "query": "Y"}))[0].text
        )
        r_diff = json.loads(
            (await mcp.call_tool("hwp_diff", {"file_path_a": str(doc), "file_path_b": str(doc_b)}))[0].text
        )
        return r_text, r_override, r_tbl, r_search, r_diff

    r_text, r_override, r_tbl, r_search, r_diff = asyncio.run(_run())
    for item in (r_text, r_tbl, r_search, r_diff):
        assert item["truncated"] is True
        assert "hint" in item
    assert "truncated" not in r_override


def test_rhwp_call_write_detection_and_export_safety(tmp_path: Path):
    doc = tmp_path / "doc.hwp"
    doc.write_bytes(b"orig")
    existing = tmp_path / "existing.hwp"
    existing.write_bytes(b"keep")
    export_dir = tmp_path / "md_out"
    export_dir.mkdir()

    backend = FakeBackend()
    mcp, _, _ = create_server(backend=backend)

    async def _run():
        # 1. Tool with `output` in schema and no output arg -> SafeWriter
        res_bm = json.loads(
            (
                await mcp.call_tool(
                    "hwp_rhwp_call",
                    {
                        "file_path": str(doc),
                        "tool_name": "hwp_add_bookmark",
                        "arguments": {"name": "bm1"},
                    },
                )
            )[0].text
        )
        assert res_bm["changed"] is True
        assert "new_sha256" in res_bm

        # 2. Export to existing file -> rejected
        with pytest.raises(Exception, match="이미 파일이 존재"):
            await mcp.call_tool(
                "hwp_rhwp_call",
                {
                    "file_path": str(doc),
                    "tool_name": "hwp_add_bookmark",
                    "arguments": {"name": "bm2", "output": str(existing)},
                },
            )

        # 3. Export to existing folder (e.g. markdown) -> allowed
        res_md = json.loads(
            (
                await mcp.call_tool(
                    "hwp_rhwp_call",
                    {
                        "file_path": str(doc),
                        "tool_name": "hwp_export_markdown",
                        "arguments": {"output": str(export_dir)},
                    },
                )
            )[0].text
        )
        assert res_md["ok"] is True

    asyncio.run(_run())


def test_rhwp_call_blocks_write_in_read_only_mode(tmp_path: Path):
    doc = tmp_path / "doc.hwp"
    doc.write_bytes(b"orig")
    mcp, _, _ = create_server(backend=FakeBackend(), read_only=True)

    async def _run():
        with pytest.raises(Exception, match="읽기 전용 모드"):
            await mcp.call_tool(
                "hwp_rhwp_call",
                {
                    "file_path": str(doc),
                    "tool_name": "hwp_add_bookmark",
                    "arguments": {"name": "bm1"},
                },
            )

    asyncio.run(_run())
