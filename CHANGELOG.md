# Changelog

All notable changes to this fork are documented here.
The upstream Agent-S changelog is at [simular-ai/Agent-S](https://github.com/simular-ai/Agent-S).

---

## [Unreleased]

---

## [0.3.2-direct.1] — 2025-03-03

### Added

- **`DirectACI` class** (`gui_agents/s3/agents/grounding.py`)
  - Single-model execution mode: one multimodal LLM handles both visual reasoning and pixel-coordinate output
  - Eliminates the need for a separate grounding model API endpoint
  - Overrides `click`, `type`, `scroll`, `drag_and_drop`, `highlight_text_span` with `(x, y)` signatures

- **`_px()` coordinate normalization** in `DirectACI`
  - Handles float 0–1 (kimi-k2.5), integer 0–1000 (qwen3.5-plus), and absolute pixels (UI-TARS) formats
  - Prevents `pyautogui.FailSafeException` when models output normalized coordinates

- **`--direct` CLI flag** (`gui_agents/s3/cli_app.py`)
  - Makes all `--ground_*` arguments optional when `--direct` is used
  - Instantiates `DirectACI` instead of `OSWorldACI`

- **OpenClaw skill** (`openclaw-skill/`)
  - `SKILL.md` manifest for the `agent-s-cua` skill
  - `scripts/run_agent_s.py` standalone runner with argument parsing and logging

- **Expanded documentation** (`USAGE.md`)
  - Full operational guide: all startup commands, model table, bug records, Python SDK examples
  - Section 13: S3 code architecture deep-dive (execution flow, per-module explanation, action table)

### Fixed

- `pyautogui.FailSafeException` when kimi-k2.5 outputs float coordinates (e.g. `0.472, 0.978`) — now normalized via `_px()` before passing to pyautogui

---

## [0.3.2] — upstream

Base version from [simular-ai/Agent-S](https://github.com/simular-ai/Agent-S).
See upstream repository for full history.
