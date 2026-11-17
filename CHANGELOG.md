# Changelog

## 0.1.0 (2026-11-17)

첫 공개 릴리스.

- `rhwp mcp-serve` 기반 헤드리스 HWP/HWPX MCP 서버 (`hwp-edit-mcp`)
- `SafeWriter` 트랜잭션: SHA-256 해시 충돌 검사, `.hwp-mcp-history` 자동 스냅샷(최대 50개), 임시 파일 재열기·무손실 검증, `os.replace` 원자 교체
- 14개 MCP 도구 제공: `hwp_info`, `hwp_get_text`, `hwp_search`, `hwp_table_view`, `hwp_fill_cells`(좌표·라벨 지원), `hwp_replace_text`, `hwp_fill_fields`, `hwp_insert_text`, `hwp_run_plan`, `hwp_render_page`, `hwp_history`, `hwp_restore`, `hwp_diff`, `hwp_rhwp_call`
- CLI 옵션(`--read-only`, `--root`, `--rhwp-path`, `install-rhwp`) 및 환경변수(`HWP_EDIT_READ_ONLY`, `HWP_EDIT_ROOTS`, `HWP_EDIT_MAX_CHARS`, `HWP_EDIT_NO_DOWNLOAD`, `HWP_EDIT_LOG_FILE`, `HWP_EDIT_CACHE_DIR`, `RHWP_EXE`) 지원
