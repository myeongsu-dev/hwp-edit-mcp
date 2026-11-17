# hwp-edit-mcp

AI 에이전트가 HWP·HWPX 문서를 고칠 때 원본을 지키는 안전한 쓰기(해시 충돌 검사, 자동 스냅샷, 재열기 검증, 원자 교체), 라벨 기반 표 채우기, 히스토리·복원·비교를 제공하는 MCP 서버입니다.

## 빠른 시작

```bash
uvx hwp-edit-mcp
```

첫 실행 시 [rhwp](https://github.com/edwardkim/rhwp) 실행 파일을 캐시에 자동으로 내려받습니다. Claude Code 등록 예:

```bash
claude mcp add -s user hwp -- uvx hwp-edit-mcp
```

다른 에이전트(Claude Desktop, Codex, Grok CLI, Antigravity, Gemini CLI, OpenCode, Cursor, VS Code) 설정은 [에이전트별 설정 안내](docs/clients.md), 문제 해결은 [트러블슈팅](docs/troubleshooting.md)을 참고하세요.

## 안전한 쓰기(SafeWriter)

모든 쓰기 도구는 `SafeWriter` 트랜잭션을 거칩니다.

1. **해시 충돌 검사**: 직전에 읽은 SHA-256 또는 `expected_sha256`과 현재 파일 해시를 대조해 외부 편집기 수정과의 충돌을 막습니다(`force=True`로 우회 가능).
2. **자동 스냅샷**: 수정 직전 원본을 문서 폴더의 `.hwp-mcp-history/<파일명>/`에 최대 50개까지 보관합니다.
3. **임시 파일 격리 및 재열기 검증**: 같은 폴더의 임시 파일에 먼저 쓴 뒤 손실 보고(`lossCount`)가 없는지 확인하고, `rhwp`로 다시 열어 페이지 수 급감이나 파손을 검사합니다(`allow_loss=True`로 허용 가능).
4. **원자 교체**: `os.replace`로 원본을 교체하며, Windows 파일 잠금(`PermissionError`) 시 짧게 대기하며 재시도합니다.

## 제공 도구 (14개)

| 이름 | 하는 일 | 구분 |
| :--- | :--- | :--- |
| `hwp_info` | 문서 메타데이터(형식, 페이지 수, 문단 수, 글꼴, SHA-256) 조회 | 읽기 |
| `hwp_get_text` | 본문 텍스트 추출 (`text` / `markdown`, 페이지·길이 지정) | 읽기 |
| `hwp_search` | 문자열 검색 및 페이지·문맥·표 셀 좌표 반환 | 읽기 |
| `hwp_table_view` | 표 크기, 병합 정보, 셀 좌표·텍스트 조회 (`table_index`) | 읽기 |
| `hwp_fill_cells` | 좌표(`row`, `col`) 또는 라벨(`label`, `right`/`below`)로 표 셀 채우기 | 쓰기 |
| `hwp_replace_text` | 본문·표 셀 텍스트 일괄 치환 | 쓰기 |
| `hwp_fill_fields` | 누름틀(필드) 이름 기준 값 채우기 | 쓰기 |
| `hwp_insert_text` | 지정한 섹션·문단·오프셋 위치에 텍스트 삽입 | 쓰기 |
| `hwp_run_plan` | rhwp 선언적 편집 계획서(plan JSON) 일괄 실행 | 쓰기 |
| `hwp_render_page` | 페이지를 PNG 또는 SVG 이미지로 렌더링 | 읽기 |
| `hwp_history` | `.hwp-mcp-history` 스냅샷 목록 최신순 조회 | 읽기 |
| `hwp_restore` | `snapshot_id`로 문서 복원 (현재 파일 백업 후 원자 교체) | 쓰기 |
| `hwp_diff` | 두 파일 또는 현재 문서와 스냅샷 간 텍스트 unified diff 비교 | 읽기 |
| `hwp_rhwp_call` | rhwp 내장 180여 개 도구 직접 호출 (쓰기 도구는 SafeWriter 경유) | 읽기/쓰기 |

## CLI 옵션 및 환경변수

| CLI 옵션 | 환경변수 | 기본값 | 설명 |
| :--- | :--- | :--- | :--- |
| `--read-only` | `HWP_EDIT_READ_ONLY` | 비활성 | 쓰기 도구를 등록하지 않고 읽기·검사 도구만 노출 |
| `--root DIR` (반복) | `HWP_EDIT_ROOTS` | 제한 없음 | 접근 허용 폴더 지정 (Windows `;`, 그 외 `:` 구분) |
| `--rhwp-path EXE` | `RHWP_EXE` | 자동 탐색/다운로드 | 사용할 `rhwp` 실행 파일 경로 지정 |
| `install-rhwp` | — | — | `rhwp` 실행 파일을 미리 내려받아 캐시에 저장 |
| — | `HWP_EDIT_MAX_CHARS` | `20000` | 도구 응답 최대 문자 수 상한 |
| — | `HWP_EDIT_NO_DOWNLOAD` | 비활성 | `rhwp` 자동 내려받기 비활성화 (오프라인 환경용) |
| — | `HWP_EDIT_CACHE_DIR` | OS 기본 캐시 | `rhwp` 캐시 저장 경로 덮어쓰기 |
| — | `HWP_EDIT_LOG_FILE` | stderr만 출력 | 서버 로그를 파일에도 기록 |

## rhwp와의 관계

`rhwp`는 `mcp-serve` 명령으로 저수준 HWP/HWPX 파싱·편집 도구를 제공합니다. `hwp-edit-mcp`는 `rhwp mcp-serve`를 상주 하위 프로세스로 감싸면서, 에이전트 실수나 덮어쓰기로부터 문서를 보호하는 `SafeWriter`(해시 충돌 검사, 스냅샷 백업·복원·diff, 재열기 무손실 검증, 원자 교체), 라벨 기반 표 셀 채우기, 허용 폴더(`--root`) 및 읽기 전용(`--read-only`) 가드, 응답 길이 제한(`max_chars`), 자동 `rhwp` 설치·캐싱을 더합니다.

## 감사의 말

이 프로젝트는 [jkf87/hwp-mcp](https://github.com/jkf87/hwp-mcp)에서 출발했습니다. "AI 에이전트가 MCP로 한글 문서를 다룬다"는 아이디어와 처음 구조는 jkf87 님의 저장소에서 왔습니다. 그 저장소를 포크해 쓰다가, 한컴오피스 없이 여러 OS에서 돌아가도록 [rhwp](https://github.com/edwardkim/rhwp) 엔진 기반으로 새로 작성해 독립 프로젝트가 되었습니다. 길을 먼저 열어 주신 jkf87 님과 rhwp를 만든 edwardkim 님께 감사드립니다.

## 라이선스

`hwp-edit-mcp`는 [MIT License](LICENSE)로 배포됩니다. 런타임에 사용하는 `rhwp`의 MIT 라이선스 고지는 [NOTICE](NOTICE)를 확인하세요.
