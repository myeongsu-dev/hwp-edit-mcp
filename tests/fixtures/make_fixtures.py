"""Generate public sample HWPX/HWP5 fixtures using rhwp."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_RHWP = "D:/40_Tools/rhwp/rhwp/rhwp.exe"

SCAFFOLD_SPEC = {
    "version": "1",
    "title": "참가 신청서",
    "blocks": [
        {"type": "paragraph", "text": "행사 참가를 위해 아래 신청서를 작성해 주세요."},
        {"type": "paragraph", "text": "모든 항목을 입력한 뒤 제출하시기 바랍니다."},
        {
            "type": "table",
            "rows": [
                ["성명", ""],
                ["소속", ""],
                ["연락처", ""],
            ],
        },
    ],
}


def resolve_rhwp(explicit: str | None = None) -> Path:
    for cand in (explicit, os.environ.get("RHWP_EXE"), shutil.which("rhwp"), DEFAULT_RHWP):
        if cand and Path(cand).is_file():
            return Path(cand).resolve()
    raise FileNotFoundError("rhwp 실행 파일을 찾을 수 없습니다. --rhwp 또는 RHWP_EXE 를 지정하세요.")


def build_fixtures(rhwp_exe: Path, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    hwpx_path = out_dir / "sample_form.hwpx"
    hwp_path = out_dir / "sample_form.hwp"

    with tempfile.TemporaryDirectory() as td:
        spec_path = Path(td) / "spec.json"
        spec_path.write_text(json.dumps(SCAFFOLD_SPEC, ensure_ascii=False, indent=2), encoding="utf-8")

        subprocess.run(
            [str(rhwp_exe), "scaffold", str(spec_path), "-o", str(hwpx_path), "--json"],
            check=True,
        )
        subprocess.run(
            [str(rhwp_exe), "convert", str(hwpx_path), str(hwp_path), "--verify", "--json"],
            check=True,
        )

    return hwpx_path, hwp_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate public HWP/HWPX test fixtures.")
    parser.add_argument("--rhwp", default=None, help="rhwp executable path (or set RHWP_EXE)")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent),
        help="Output directory (default: tests/fixtures)",
    )
    args = parser.parse_args(argv)

    rhwp_exe = resolve_rhwp(args.rhwp)
    hwpx_path, hwp_path = build_fixtures(rhwp_exe, Path(args.out_dir))
    print(f"Generated: {hwpx_path} ({hwpx_path.stat().st_size} bytes)")
    print(f"Generated: {hwp_path} ({hwp_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main(sys.argv[1:])
