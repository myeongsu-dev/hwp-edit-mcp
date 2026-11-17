# 트러블슈팅

| 증상 | 원인 | 해결 |
| :--- | :--- | :--- |
| `rhwp` 내려받기 실패 또는 오프라인 환경에서 기동 불가 | 네트워크 차단, 프록시, GitHub 릴리스 접근 실패 | 미리 받은 `rhwp` 경로를 `RHWP_EXE`(또는 `--rhwp-path`)로 지정하고, 자동 다운로드를 끄려면 `HWP_EDIT_NO_DOWNLOAD=1`을 설정합니다. |
| Windows에서 `"Connection closed"` 오류 | 첫 실행 시 `rhwp` 다운로드·압축 해제로 기동이 지연되거나, `uvx` 캐시·경로 문제로 stdio가 먼저 닫힘 | 터미널에서 `uvx hwp-edit-mcp install-rhwp`를 먼저 실행해 바이너리를 캐시에 받아 둔 뒤 에이전트를 다시 시작합니다. `HWP_EDIT_LOG_FILE`로 로그 경로를 지정해 stderr 원인을 확인합니다. |
| 에이전트에서 기동/도구 호출 시간 초과(timeout) | 대용량 문서 처리 또는 초기 `rhwp` 다운로드 시간 초과 | `uvx hwp-edit-mcp install-rhwp`를 사전 실행하고, Codex·Grok CLI 등에서는 `startup_timeout_sec = 30`, `tool_timeout_sec = 60` 이상으로 설정합니다. |
| `HashConflictError` 발생 | 서버가 문서를 읽은 뒤 한컴오피스 등 외부 편집기에서 파일이 저장되어 SHA-256 해시가 달라짐 | `hwp_info`나 `hwp_get_text`로 최신 문서를 다시 읽은 뒤 수정합니다. 외부 변경을 덮어써야 할 때만 `force=True`를 전달합니다. |
| `PermissionError` (허용 폴더 밖 경로) | `--root` 또는 `HWP_EDIT_ROOTS`로 지정한 허용 폴더 바깥의 파일에 접근함 | 허용된 폴더 안의 파일만 사용하거나, 서버 실행 인자에 `--root <폴더>`(또는 `HWP_EDIT_ROOTS`)를 추가합니다. |
| `FileLockedError` 발생 | 한컴오피스 등 다른 프로그램이 대상 파일을 잠그고 있어 `os.replace`가 실패함 | 열려 있는 편집기에서 해당 문서를 닫은 뒤 다시 실행합니다. 실패 직전 원본은 `.hwp-mcp-history` 스냅샷으로 보존되어 있습니다. |
| 응답이 잘림 (`truncated` 표시) | 도구 출력이 `max_chars`(기본 `20000`, `HWP_EDIT_MAX_CHARS`)를 초과함 | `hwp_get_text`에서는 `page`나 `max_chars`를 지정해 나누어 읽고, `hwp_table_view`에서는 `table_index`로 필요한 표만 조회합니다. 필요 시 `HWP_EDIT_MAX_CHARS` 값을 높입니다. |
