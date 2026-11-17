"""Tests for rhwp_install.ensure_rhwp and lazy RhwpBackend resolution."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import pytest

from hwp_edit_mcp import rhwp_install
from hwp_edit_mcp.rhwp_backend import RhwpBackend


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_zip(entries: dict[str, bytes], symlinks: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        for name, target in (symlinks or {}).items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3  # Unix
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, target)
    return buf.getvalue()


def _make_targz(entries: dict[str, bytes], symlinks: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        for name, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name=name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tf.addfile(info)
    return buf.getvalue()


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("HWP_EDIT_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("RHWP_EXE", raising=False)
    monkeypatch.delenv("HWP_EDIT_NO_DOWNLOAD", raising=False)
    monkeypatch.setenv("PATH", "")
    return cache_dir


def test_explicit_and_rhwp_exe_priority_and_missing_error(isolated_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    explicit_exe = tmp_path / "explicit_rhwp.exe"
    explicit_exe.write_bytes(b"explicit")
    env_exe = tmp_path / "env_rhwp.exe"
    env_exe.write_bytes(b"env")

    monkeypatch.setenv("RHWP_EXE", str(env_exe))
    assert rhwp_install.ensure_rhwp(str(explicit_exe), allow_download=False) == explicit_exe.resolve()
    assert rhwp_install.ensure_rhwp(None, allow_download=False) == env_exe.resolve()

    # Missing explicit path must fail immediately without falling back to RHWP_EXE
    missing_explicit = tmp_path / "no_such_explicit.exe"
    with pytest.raises(FileNotFoundError) as exc_info:
        rhwp_install.ensure_rhwp(str(missing_explicit), allow_download=False)
    assert str(missing_explicit) in str(exc_info.value)

    # Missing RHWP_EXE must fail immediately without falling back to cache/download
    missing_env = tmp_path / "no_such_env.exe"
    monkeypatch.setenv("RHWP_EXE", str(missing_env))
    with pytest.raises(FileNotFoundError) as exc_info:
        rhwp_install.ensure_rhwp(None, allow_download=True)
    assert str(missing_env) in str(exc_info.value)


def test_cached_binary_skips_download(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    exe_name = rhwp_install._exe_name()
    cached = isolated_env / "rhwp" / rhwp_install.RHWP_VERSION / exe_name
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"cached-rhwp")

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("urlopen should not be called when cached")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    assert rhwp_install.ensure_rhwp(allow_download=True) == cached.resolve()


def test_install_from_fake_zip(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rhwp_install.sys, "platform", "win32")
    monkeypatch.setattr(rhwp_install.platform, "system", lambda: "Windows")
    monkeypatch.setattr(rhwp_install.platform, "machine", lambda: "AMD64")

    asset = f"rhwp-{rhwp_install.RHWP_VERSION}-windows-x86_64.zip"
    zip_bytes = _make_zip({"rhwp/rhwp.exe": b"fake-win-exe", "rhwp/README.md": b"hi"})
    digest = hashlib.sha256(zip_bytes).hexdigest()
    sums = f"{digest}  {asset}\n".encode("utf-8")

    def fake_urlopen(url: str, timeout: float = 60):
        if url.endswith("/SHA256SUMS.txt"):
            return _FakeResponse(sums)
        if url.endswith(f"/{asset}"):
            return _FakeResponse(zip_bytes)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    installed = rhwp_install.ensure_rhwp(allow_download=True)
    assert installed.is_file()
    assert installed.name == "rhwp.exe"
    assert installed.read_bytes() == b"fake-win-exe"
    assert installed.parent == (isolated_env / "rhwp" / rhwp_install.RHWP_VERSION).resolve()


def test_install_from_fake_targz(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rhwp_install.sys, "platform", "linux")
    monkeypatch.setattr(rhwp_install.platform, "system", lambda: "Linux")
    monkeypatch.setattr(rhwp_install.platform, "machine", lambda: "x86_64")

    asset = f"rhwp-{rhwp_install.RHWP_VERSION}-linux-x86_64.tar.gz"
    tar_bytes = _make_targz({"rhwp/rhwp": b"fake-linux-bin"})
    digest = hashlib.sha256(tar_bytes).hexdigest()
    sums = f"{digest}  {asset}\n".encode("utf-8")

    def fake_urlopen(url: str, timeout: float = 60):
        if url.endswith("/SHA256SUMS.txt"):
            return _FakeResponse(sums)
        if url.endswith(f"/{asset}"):
            return _FakeResponse(tar_bytes)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    installed = rhwp_install.ensure_rhwp(allow_download=True)
    assert installed.is_file()
    assert installed.name == "rhwp"
    assert installed.read_bytes() == b"fake-linux-bin"
    if os.name != "nt":
        assert installed.stat().st_mode & 0o111


def test_sha256_mismatch_leaves_cache_empty(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rhwp_install.sys, "platform", "win32")
    monkeypatch.setattr(rhwp_install.platform, "system", lambda: "Windows")
    monkeypatch.setattr(rhwp_install.platform, "machine", lambda: "AMD64")

    asset = f"rhwp-{rhwp_install.RHWP_VERSION}-windows-x86_64.zip"
    zip_bytes = _make_zip({"rhwp/rhwp.exe": b"fake-win-exe"})
    wrong_sums = f"{'0' * 64}  {asset}\n".encode("utf-8")

    def fake_urlopen(url: str, timeout: float = 60):
        if url.endswith("/SHA256SUMS.txt"):
            return _FakeResponse(wrong_sums)
        if url.endswith(f"/{asset}"):
            return _FakeResponse(zip_bytes)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="SHA256"):
        rhwp_install.ensure_rhwp(allow_download=True)

    assert not (isolated_env / "rhwp").exists()


def test_path_traversal_and_symlink_rejected(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rhwp_install.sys, "platform", "win32")
    monkeypatch.setattr(rhwp_install.platform, "system", lambda: "Windows")
    monkeypatch.setattr(rhwp_install.platform, "machine", lambda: "AMD64")

    asset = f"rhwp-{rhwp_install.RHWP_VERSION}-windows-x86_64.zip"
    for bad_zip in (
        _make_zip({"../evil.exe": b"evil", "rhwp/rhwp.exe": b"ok"}),
        _make_zip({"/abs/evil.exe": b"evil", "rhwp/rhwp.exe": b"ok"}),
        _make_zip({"rhwp/rhwp.exe": b"ok"}, symlinks={"rhwp/link": "/etc/passwd"}),
    ):
        digest = hashlib.sha256(bad_zip).hexdigest()
        sums = f"{digest}  {asset}\n".encode("utf-8")

        def fake_urlopen(url: str, timeout: float = 60, data=bad_zip, s=sums):
            if url.endswith("/SHA256SUMS.txt"):
                return _FakeResponse(s)
            return _FakeResponse(data)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(ValueError):
            rhwp_install.ensure_rhwp(allow_download=True)
        assert not (isolated_env / "rhwp").exists()


def test_no_download_env_raises_without_network(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HWP_EDIT_NO_DOWNLOAD", "1")

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("urlopen must not be called when HWP_EDIT_NO_DOWNLOAD=1")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    with pytest.raises(FileNotFoundError, match="install-rhwp"):
        rhwp_install.ensure_rhwp(allow_download=True)


def test_rhwp_backend_init_is_lazy(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HWP_EDIT_NO_DOWNLOAD", "1")
    backend = RhwpBackend()
    assert backend.exe_path is None

    with pytest.raises(FileNotFoundError):
        asyncio.run(backend.start())

    with pytest.raises(FileNotFoundError):
        asyncio.run(backend.run_cli(["--version"]))
