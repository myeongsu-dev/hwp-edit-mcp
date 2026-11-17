"""Locate and optionally download the pinned rhwp executable."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

RHWP_VERSION = "v0.9.0"
RELEASE_BASE_URL = f"https://github.com/edwardkim/rhwp/releases/download/{RHWP_VERSION}"
DOWNLOAD_TIMEOUT = 60

_ASSET_MAP = {
    ("windows", "x86_64"): f"rhwp-{RHWP_VERSION}-windows-x86_64.zip",
    ("linux", "x86_64"): f"rhwp-{RHWP_VERSION}-linux-x86_64.tar.gz",
    ("linux", "aarch64"): f"rhwp-{RHWP_VERSION}-linux-aarch64.tar.gz",
    ("darwin", "x86_64"): f"rhwp-{RHWP_VERSION}-macos-x86_64.tar.gz",
    ("darwin", "aarch64"): f"rhwp-{RHWP_VERSION}-macos-aarch64.tar.gz",
}


def _exe_name() -> str:
    return "rhwp.exe" if sys.platform == "win32" else "rhwp"


def _select_asset(system: Optional[str] = None, machine: Optional[str] = None) -> str:
    sys_name = (system or platform.system()).strip().lower()
    mach_raw = (machine or platform.machine()).strip().lower()
    if mach_raw in ("amd64", "x86_64", "x64"):
        mach = "x86_64"
    elif mach_raw in ("arm64", "aarch64"):
        mach = "aarch64"
    else:
        mach = mach_raw

    asset = _ASSET_MAP.get((sys_name, mach))
    if not asset:
        raise RuntimeError(
            f"지원하지 않는 플랫폼입니다: {system or platform.system()} / {machine or platform.machine()}"
        )
    return asset


def _cache_root() -> Path:
    override = os.environ.get("HWP_EDIT_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else (Path.home() / "AppData" / "Local")
        return base / "hwp-edit-mcp"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "hwp-edit-mcp"
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(xdg) if xdg else (Path.home() / ".cache")
    return base / "hwp-edit-mcp"


def _no_download() -> bool:
    return os.environ.get("HWP_EDIT_NO_DOWNLOAD", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _download_bytes(url: str, timeout: float = DOWNLOAD_TIMEOUT) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"rhwp 다운로드 실패 ({url}): {exc}") from exc


def _parse_sha256sums(text: str, asset: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0], parts[1].lstrip("*").strip()
        if name.startswith("./"):
            name = name[2:]
        if name == asset or Path(name).name == asset:
            return digest.lower()
    raise RuntimeError(f"SHA256SUMS.txt에서 '{asset}' 항목을 찾을 수 없습니다.")


def _validate_member_path(name: str, dest_dir: Path) -> None:
    norm = name.replace("\\", "/")
    if not norm or norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        raise ValueError(f"절대 경로 압축 항목이 거부되었습니다: {name}")
    if ".." in norm.split("/"):
        raise ValueError(f"상위 경로(..) 압축 항목이 거부되었습니다: {name}")
    dest_root = dest_dir.resolve()
    target = (dest_dir / norm).resolve()
    if target != dest_root and not target.is_relative_to(dest_root):
        raise ValueError(f"대상 폴더를 벗어나는 압축 항목이 거부되었습니다: {name}")


def _safe_extract(archive_path: Path, dest_dir: Path, is_zip: bool) -> None:
    if is_zip:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                _validate_member_path(info.filename, dest_dir)
                if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                    raise ValueError(f"심볼릭 링크 압축 항목이 거부되었습니다: {info.filename}")
            zf.extractall(dest_dir)
    else:
        with tarfile.open(archive_path, "r:*") as tf:
            for member in tf.getmembers():
                _validate_member_path(member.name, dest_dir)
                if member.issym() or member.islnk():
                    raise ValueError(f"링크 압축 항목이 거부되었습니다: {member.name}")
            if hasattr(tarfile, "data_filter"):
                tf.extractall(dest_dir, filter="data")
            else:
                tf.extractall(dest_dir)


def _download_and_install(target_dir: Path, exe_name: str) -> Path:
    asset = _select_asset()
    sums_url = f"{RELEASE_BASE_URL}/SHA256SUMS.txt"
    asset_url = f"{RELEASE_BASE_URL}/{asset}"

    sums_text = _download_bytes(sums_url).decode("utf-8", errors="replace")
    expected_sha = _parse_sha256sums(sums_text, asset)
    archive_bytes = _download_bytes(asset_url)

    actual_sha = hashlib.sha256(archive_bytes).hexdigest().lower()
    if actual_sha != expected_sha:
        raise RuntimeError(
            f"다운로드한 {asset}의 SHA256 해시가 일치하지 않습니다. "
            f"(기대: {expected_sha}, 실제: {actual_sha})"
        )

    with tempfile.TemporaryDirectory(prefix="rhwp-dl-") as tmp_str:
        tmp_dir = Path(tmp_str)
        archive_path = tmp_dir / asset
        archive_path.write_bytes(archive_bytes)

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()
        _safe_extract(archive_path, extract_dir, is_zip=asset.endswith(".zip"))

        found_exe: Optional[Path] = None
        for match in sorted(extract_dir.rglob(exe_name)):
            if match.is_file():
                found_exe = match
                break
        if found_exe is None:
            raise RuntimeError(f"압축 해제된 파일에서 '{exe_name}'을 찾을 수 없습니다.")

        target_dir.mkdir(parents=True, exist_ok=True)
        target_exe = target_dir / exe_name
        fd, staged_str = tempfile.mkstemp(dir=target_dir, prefix=f".{exe_name}.", suffix=".tmp")
        os.close(fd)
        staged_path = Path(staged_str)
        try:
            shutil.copy2(found_exe, staged_path)
            if os.name != "nt":
                os.chmod(staged_path, 0o755)
            os.replace(staged_path, target_exe)
        except BaseException:
            staged_path.unlink(missing_ok=True)
            raise

    return target_exe.resolve()


def ensure_rhwp(explicit: Optional[str] = None, allow_download: bool = True) -> Path:
    """Return a usable rhwp executable path, downloading the pinned release if needed."""
    if explicit:
        cand = Path(explicit)
        if cand.is_file():
            return cand.resolve()
        raise FileNotFoundError(f"지정한 rhwp 실행 파일을 찾을 수 없습니다: {explicit}")

    env_exe = os.environ.get("RHWP_EXE", "").strip()
    if env_exe:
        cand = Path(env_exe)
        if cand.is_file():
            return cand.resolve()
        raise FileNotFoundError(f"RHWP_EXE 환경변수가 가리키는 파일을 찾을 수 없습니다: {env_exe}")

    which_hit = shutil.which("rhwp.exe") or shutil.which("rhwp")
    if which_hit:
        return Path(which_hit).resolve()

    exe_name = _exe_name()
    target_dir = _cache_root() / "rhwp" / RHWP_VERSION
    cached_exe = target_dir / exe_name
    if cached_exe.is_file():
        return cached_exe.resolve()

    if allow_download and not _no_download():
        return _download_and_install(target_dir, exe_name)

    try:
        manual_link = f"{RELEASE_BASE_URL}/{_select_asset()}"
    except RuntimeError:
        manual_link = f"https://github.com/edwardkim/rhwp/releases/tag/{RHWP_VERSION}"

    raise FileNotFoundError(
        "rhwp 실행 파일을 찾을 수 없습니다. 다음 중 한 가지 방법으로 해결하세요:\n"
        "1) RHWP_EXE 환경변수에 rhwp 실행 파일 경로를 지정\n"
        "2) `hwp-edit-mcp install-rhwp` 명령으로 자동 설치\n"
        f"3) 오프라인 환경에서는 릴리스({manual_link})를 내려받아 수동 설치"
    )
