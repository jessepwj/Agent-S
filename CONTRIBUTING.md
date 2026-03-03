# Contributing to AutoAct

Thank you for your interest in contributing. This document covers how to get set up, what to work on, and how to submit changes.

## Table of Contents

- [Getting Started](#getting-started)
- [What to Work On](#what-to-work-on)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)

---

## Getting Started

### Prerequisites

- Python 3.9 – 3.12
- Windows, macOS, or Linux
- A DashScope / OpenAI-compatible API key for testing

### Setup

```bash
git clone https://github.com/jessepwj/Agent-S
cd Agent-S
pip install -e ".[dev]"
```

Verify the install:

```bash
agent_s --help
```

---

## What to Work On

Good first contributions:

| Area | Description |
|------|-------------|
| Model testing | Test DirectACI with Gemini, Claude, Qwen-VL, and report coordinate format used |
| Resolution fixes | Verify `_px()` normalization is correct on non-1080p screens |
| OpenClaw skill | Improve `SKILL.md` documentation, add new invocation patterns |
| Examples | Add example scripts to `examples/` for common use cases |
| macOS / Linux | Test and fix platform-specific behavior in `grounding.py` |
| Error handling | Better error messages when model outputs malformed actions |

Open issues are tracked in the [GitHub Issues](https://github.com/jessepwj/Agent-S/issues) tab.

---

## Development Workflow

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes.** Keep commits focused — one logical change per commit.

3. **Format** before committing:
   ```bash
   black gui_agents
   ```

4. **Test manually** — there are no automated unit tests; test by running the agent on a real task.

5. **Push** and open a pull request.

---

## Code Style

- Formatting: [Black](https://github.com/psf/black) (enforced by CI)
- Line length: Black default (88)
- All new files must pass `black --check`
- Docstrings on public methods are appreciated but not required

### Important patterns

**`@agent_action` decorator** — any method on `OSWorldACI` or `DirectACI` decorated with `@agent_action` will be automatically included in the model's system prompt via `inspect.signature()`. Changing the method signature or docstring directly changes the model's behavior.

**Coordinate handling** — all coordinate math in `DirectACI` goes through `_px(x, y)`. Do not call `pyautogui` directly with raw model output.

---

## Submitting a Pull Request

1. Fill in the PR template completely.
2. Link any related issues with `Closes #123`.
3. Keep the diff focused — avoid unrelated cleanup in the same PR.
4. CI runs `black --check` on Python 3.10 and 3.11; ensure it passes before requesting review.

---

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Please include:

- OS and Python version
- Model used (`--model`, `--provider`, `--direct` or not)
- The task instruction
- Full error output or unexpected behavior description
- Steps to reproduce
