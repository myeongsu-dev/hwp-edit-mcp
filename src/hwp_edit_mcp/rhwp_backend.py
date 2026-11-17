"""rhwp backend client (mcp-serve stdio proxy + CLI fallback)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from hwp_edit_mcp.rhwp_install import ensure_rhwp

logger = logging.getLogger("hwp-edit-mcp.rhwp-backend")


class RhwpError(RuntimeError):
    """Base error for rhwp backend failures."""


class RhwpToolError(RhwpError):
    """Raised when rhwp returns an error result (isError=True or non-zero exit)."""

    def __init__(self, message: str, data: Optional[Any] = None):
        super().__init__(message)
        self.data = data


def _parse_tool_output(raw_text: str) -> Any:
    text = raw_text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": raw_text}


class RhwpBackend:
    """Persistent stdio MCP proxy to `rhwp.exe mcp-serve` with CLI helper.

    Owns the `stdio_client` + `ClientSession` inside a dedicated asyncio Task so
    anyio cancel scopes are always entered and exited in the exact same task.
    """

    def __init__(self, exe_path: Optional[str] = None, default_timeout: float = 30.0):
        self._explicit = exe_path
        self.exe_path: Optional[Path] = None
        self.default_timeout = default_timeout
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._queue: Optional[asyncio.Queue[Tuple[str, Any, asyncio.Future[Any]]]] = None
        self._server_info: Optional[Dict[str, Any]] = None

    async def _ensure_exe(self) -> Path:
        if self.exe_path is None:
            self.exe_path = await asyncio.to_thread(ensure_rhwp, self._explicit)
        return self.exe_path

    @property
    def is_connected(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()

    async def start(self) -> None:
        """Start the dedicated worker task and wait until `rhwp.exe mcp-serve` is initialized."""
        if self.is_connected:
            return

        exe = await self._ensure_exe()
        queue: asyncio.Queue[Tuple[str, Any, asyncio.Future[Any]]] = asyncio.Queue()
        ready_fut: asyncio.Future[Dict[str, Any]] = asyncio.get_running_loop().create_future()

        async def _worker() -> None:
            params = StdioServerParameters(
                command=str(exe),
                args=["mcp-serve"],
                env=os.environ.copy(),
            )
            try:
                async with stdio_client(params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        init_res = await asyncio.wait_for(session.initialize(), timeout=15.0)
                        info = {
                            "name": init_res.serverInfo.name if init_res.serverInfo else "rhwp",
                            "version": init_res.serverInfo.version if init_res.serverInfo else "unknown",
                        }
                        self._server_info = info
                        logger.info("Connected to rhwp mcp-serve: %s (%s)", self.exe_path, info)
                        if not ready_fut.done():
                            ready_fut.set_result(info)

                        while True:
                            op, payload, fut = await queue.get()
                            if op == "stop":
                                if not fut.done():
                                    fut.set_result(None)
                                break
                            try:
                                if op == "list_tools":
                                    res = await session.list_tools()
                                elif op == "call_tool":
                                    name, args = payload
                                    res = await session.call_tool(name, args)
                                else:
                                    raise ValueError(f"Unknown op: {op}")
                                if not fut.done():
                                    fut.set_result(res)
                            except BaseException as exc:
                                if not fut.done():
                                    fut.set_exception(exc)
            except BaseException as exc:
                if not ready_fut.done():
                    ready_fut.set_exception(exc)
                # Drain pending futures
                while not queue.empty():
                    _, _, fut = queue.get_nowait()
                    if not fut.done():
                        fut.set_exception(exc)

        self._queue = queue
        self._worker_task = asyncio.create_task(_worker())
        await ready_fut

    async def close(self) -> None:
        """Shut down the persistent `rhwp.exe mcp-serve` subprocess cleanly."""
        async with self._lock:
            await self._close_unlocked()

    async def _close_unlocked(self) -> None:
        if self._worker_task is not None and not self._worker_task.done() and self._queue is not None:
            fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            await self._queue.put(("stop", None, fut))
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except Exception:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except BaseException:
                    pass
        self._worker_task = None
        self._queue = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions exposed by `rhwp.exe mcp-serve`."""
        async with self._lock:
            await self.start()
            assert self._queue is not None
            fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            await self._queue.put(("list_tools", None, fut))
            res = await asyncio.wait_for(fut, timeout=self.default_timeout)
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in res.tools
            ]

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on the persistent `rhwp.exe mcp-serve` session."""
        args = {k: v for k, v in (arguments or {}).items() if v is not None}
        effective_timeout = timeout or self.default_timeout

        async with self._lock:
            for attempt in range(2):
                try:
                    await self.start()
                    assert self._queue is not None
                    fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
                    await self._queue.put(("call_tool", (name, args), fut))
                    res = await asyncio.wait_for(fut, timeout=effective_timeout)
                    break
                except (BrokenPipeError, EOFError, ConnectionError, OSError) as exc:
                    logger.warning("rhwp mcp-serve connection lost (%s), reconnecting...", exc)
                    await self._close_unlocked()
                    if attempt == 1:
                        raise RhwpError(f"rhwp mcp-serve 연결 실패: {exc}") from exc
                except asyncio.TimeoutError as exc:
                    await self._close_unlocked()
                    raise RhwpError(
                        f"rhwp 도구 '{name}' 실행 시간 초과 ({effective_timeout}s)"
                    ) from exc

            texts = [getattr(c, "text", str(c)) for c in (res.content or [])]
            joined = "\n".join(texts)
            parsed = _parse_tool_output(joined)
            if res.isError:
                msg = parsed.get("error") if isinstance(parsed, dict) else None
                raise RhwpToolError(msg or joined or f"rhwp tool '{name}' failed", data=parsed)
            return parsed

    async def run_cli(
        self,
        args: List[str],
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run `rhwp.exe` CLI directly (used for flags not exposed in mcp-serve, e.g. export-png -p)."""
        effective_timeout = timeout or self.default_timeout
        kwargs: Dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        exe = await self._ensure_exe()
        proc = await asyncio.create_subprocess_exec(str(exe), *args, **kwargs)
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=effective_timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RhwpError(f"rhwp CLI 실행 시간 초과 ({effective_timeout}s): {args[:2]}") from exc

        stdout = stdout_b.decode("utf-8", errors="replace").strip()
        stderr = stderr_b.decode("utf-8", errors="replace").strip()

        if proc.returncode not in (0, 3, 4):
            raise RhwpToolError(stderr or stdout or f"rhwp CLI exited with code {proc.returncode}")

        if stdout:
            try:
                data = json.loads(stdout)
                if isinstance(data, dict):
                    data.setdefault("_exit_code", proc.returncode)
                return data
            except json.JSONDecodeError:
                return {"text": stdout, "stderr": stderr, "_exit_code": proc.returncode}
        return {"stderr": stderr, "_exit_code": proc.returncode}
