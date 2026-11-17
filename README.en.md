# hwp-edit-mcp

An MCP server for AI agents to safely read and edit HWP/HWPX documents—featuring hash-conflict checks, automatic snapshots, reopen verification, atomic file replacement, label-based table filling, and history/restore/diff.

## Quick Start

```bash
uvx hwp-edit-mcp
```

On first run, `hwp-edit-mcp` downloads and caches the [rhwp](https://github.com/edwardkim/rhwp) binary automatically. Register in Claude Code:

```bash
claude mcp add -s user hwp -- uvx hwp-edit-mcp
```

For other clients (Claude Desktop, Codex, Grok CLI, Antigravity, Gemini CLI, OpenCode, Cursor, VS Code), see [docs/clients.md](docs/clients.md). For common issues, see [docs/troubleshooting.md](docs/troubleshooting.md).

## SafeWriter

Every write tool runs inside a `SafeWriter` transaction:

1. **Hash Conflict Check**: Compares the file's current SHA-256 against the last-seen hash or `expected_sha256` to prevent overwriting external edits (`force=True` overrides).
2. **Automatic Snapshot**: Copies the original file to `.hwp-mcp-history/<filename>/` before writing (up to 50 snapshots).
3. **Temp Isolation & Reopen Verification**: Writes to a temp file in the same directory, rejects non-zero `lossCount` (`allow_loss=True` overrides), and reopens the output via `rhwp` to verify integrity.
4. **Atomic Replace**: Swaps the temp file into place with `os.replace`, retrying briefly if locked on Windows.

## Tools (14)

| Tool | Description | Mode |
| :--- | :--- | :--- |
| `hwp_info` | Read metadata (format, pages, paragraphs, fonts, SHA-256) | Read |
| `hwp_get_text` | Extract text (`text` or `markdown`, optional `page` / `max_chars`) | Read |
| `hwp_search` | Search text and return page, context, and table cell coordinates | Read |
| `hwp_table_view` | Inspect table dimensions, merges, and cell coordinates/text | Read |
| `hwp_fill_cells` | Fill table cells by `(row, col)` or by `label` (`right` / `below`) | Write |
| `hwp_replace_text` | Find and replace text across body and table cells | Write |
| `hwp_fill_fields` | Fill click-here fields by field name | Write |
| `hwp_insert_text` | Insert text at `(section, paragraph, offset)` | Write |
| `hwp_run_plan` | Execute a declarative `rhwp` edit plan JSON | Write |
| `hwp_render_page` | Render pages to PNG or SVG images | Read |
| `hwp_history` | List `.hwp-mcp-history` snapshots (newest first) | Read |
| `hwp_restore` | Restore a document from `snapshot_id` (backs up current first) | Write |
| `hwp_diff` | Unified text diff between two files or a file and a snapshot | Read |
| `hwp_rhwp_call` | Escape hatch to any of ~180 `rhwp` tools (writes go via SafeWriter) | Read/Write |

## CLI Options & Environment Variables

| CLI Option | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `--read-only` | `HWP_EDIT_READ_ONLY` | off | Register read/inspect tools only |
| `--root DIR` (repeatable) | `HWP_EDIT_ROOTS` | unrestricted | Restrict file access (`;` on Windows, `:` otherwise) |
| `--rhwp-path EXE` | `RHWP_EXE` | auto-detect/download | Explicit `rhwp` executable path |
| `install-rhwp` | — | — | Pre-download and cache `rhwp` |
| — | `HWP_EDIT_MAX_CHARS` | `20000` | Maximum response character limit |
| — | `HWP_EDIT_NO_DOWNLOAD` | off | Disable automatic `rhwp` download |
| — | `HWP_EDIT_CACHE_DIR` | OS cache dir | Override `rhwp` cache directory |
| — | `HWP_EDIT_LOG_FILE` | stderr only | Also write server logs to a file |

## Relationship to rhwp

`hwp-edit-mcp` wraps `rhwp mcp-serve` as a persistent stdio backend and adds `SafeWriter` (hash-conflict detection, snapshot history/restore/diff, reopen verification, atomic replace), label-based table cell filling, `--root` / `--read-only` guards, response size capping, and automatic `rhwp` installation.

## License

`hwp-edit-mcp` is licensed under the [MIT License](LICENSE). See [NOTICE](NOTICE) for `rhwp` MIT license attribution.
