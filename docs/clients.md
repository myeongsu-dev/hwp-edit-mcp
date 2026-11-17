# 에이전트별 MCP 등록 안내

등록 이름은 `hwp`, 기본 실행 명령은 `uvx hwp-edit-mcp`입니다.

> [!TIP]
> 첫 실행 시 `rhwp` 바이너리를 내려받으므로 초기 기동에 수 초 이상 걸릴 수 있습니다. 기동 시간 제한이 짧은 에이전트에서는 터미널에서 아래 명령을 먼저 실행해 캐시에 받아 두세요.
> ```bash
> uvx hwp-edit-mcp install-rhwp
> ```

접근 폴더를 제한하거나 읽기 전용으로 실행하려면 `args`에 `--root <폴더>` 또는 `--read-only`를 추가합니다.

---

## Claude Code

CLI로 전역 등록:

```bash
claude mcp add -s user hwp -- uvx hwp-edit-mcp
```

프로젝트 단위 `.mcp.json`:

```json
{
  "mcpServers": {
    "hwp": {
      "command": "uvx",
      "args": ["hwp-edit-mcp"]
    }
  }
}
```

## Claude Desktop

`claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`, macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hwp": {
      "command": "uvx",
      "args": ["hwp-edit-mcp"]
    }
  }
}
```

## Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.hwp]
command = "uvx"
args = ["hwp-edit-mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 60
default_tools_approval_mode = "approve"
```

Codex는 쓰기 도구(`destructiveHint`)를 부를 때 승인을 요구합니다. `codex exec`처럼 승인 창이 없는 실행에서는 `default_tools_approval_mode = "approve"`가 있어야 쓰기 도구가 실행됩니다. 대화형으로 쓰면서 매번 확인받고 싶으면 이 줄을 뺍니다.

## Grok CLI

`~/.grok/config.toml`:

```toml
[mcp_servers.hwp]
command = "uvx"
args = ["hwp-edit-mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 60
```

## Antigravity · AGY

`~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "hwp": {
      "command": "uvx",
      "args": ["hwp-edit-mcp"]
    }
  }
}
```

## Gemini CLI

`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "hwp": {
      "command": "uvx",
      "args": ["hwp-edit-mcp"]
    }
  }
}
```

## OpenCode

`~/.config/opencode/opencode.json` (또는 프로젝트 `opencode.json`):

```json
{
  "mcp": {
    "hwp": {
      "type": "local",
      "command": ["uvx", "hwp-edit-mcp"],
      "enabled": true
    }
  }
}
```

## Cursor

`~/.cursor/mcp.json` (또는 프로젝트 `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "hwp": {
      "command": "uvx",
      "args": ["hwp-edit-mcp"]
    }
  }
}
```

## VS Code

프로젝트 `.vscode/mcp.json`:

```json
{
  "servers": {
    "hwp": {
      "command": "uvx",
      "args": ["hwp-edit-mcp"]
    }
  }
}
```

---

## 검증 결과

시나리오: `hwp_info` → `hwp_fill_cells`(라벨 "성명") → `hwp_get_text`로 확인 → `hwp_history` → `hwp_restore` → `hwp_get_text`로 원상 복구 확인. 끝난 뒤 문서 해시가 원본과 같고 스냅샷이 2개 생겼는지로 판정했습니다. (Windows 11, 샘플 `tests/fixtures/sample_form.hwp`)

| 에이전트 | 버전 | 날짜 | 결과 |
| :--- | :--- | :--- | :--- |
| Claude Code | 2.1.326 | 2026-11-17 | 통과 |
| Codex | 0.169.0 | 2026-11-17 | 통과 (`default_tools_approval_mode = "approve"` 필요) |
| Grok CLI | 1.0.88 | 2026-11-17 | 통과 |
| Antigravity (AGY) | 1.5.10 | 2026-11-17 | 통과 |
| Gemini CLI | 0.68.0 | 2026-11-17 | 통과 |
| OpenCode | 2.3.0 | 2026-11-17 | 통과 |
| Claude Desktop | — | — | 검증 예정 |
| Cursor | — | — | 검증 예정 |
| VS Code | — | — | 검증 예정 |
