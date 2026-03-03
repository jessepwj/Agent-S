<h1 align="center">
  AutoAct
</h1>

<p align="center">
  <strong>Single-model GUI automation &mdash; one model sees, reasons, and acts.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/model-kimi--k2.5%20%7C%20qwen3.5-orange" alt="Models">
  <img src="https://img.shields.io/badge/OpenClaw-skill%20ready-purple" alt="OpenClaw">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#directaci-architecture">Architecture</a> &bull;
  <a href="#openclaw-skill">OpenClaw Skill</a> &bull;
  <a href="#models">Models</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

---

AutoAct is a community-enhanced fork of [Agent-S](https://github.com/simular-ai/Agent-S) (S3, SOTA 72.60% on OSWorld) that introduces two key contributions:

1. **DirectACI** &mdash; a single-model execution mode where one multimodal LLM handles both visual reasoning *and* pixel-coordinate output, eliminating the need for a separate grounding model endpoint.
2. **OpenClaw Skill** &mdash; a plug-and-play `agent-s-cua` skill for the [OpenClaw](https://openclaw.ai) platform, enabling desktop automation in one line.

**Why DirectACI?** The original Agent-S uses two models: a reasoning LLM that describes *what* to click, plus a separate grounding model that converts that description to pixel coordinates. DirectACI feeds the screenshot directly to one capable model (e.g. kimi-k2.5) and asks it to output coordinates immediately &mdash; fewer API calls, lower latency, simpler setup.

```
Standard mode:   Screenshot --> Reasoning LLM --> "click the Send button" --> Grounding API --> (x, y) --> pyautogui
DirectACI mode:  Screenshot --> kimi-k2.5 -------------------------------------------------> (x, y) --> pyautogui
```

---

## Quick Start

### Install

```bash
git clone https://github.com/jessepwj/Agent-S
cd Agent-S
pip install -e .
```

### Run a task (DirectACI, single model)

```bash
# Set your API key (DashScope / Alibaba Cloud)
export OPENAI_API_KEY=sk-...

agent_s \
  --provider openai \
  --model kimi-k2.5 \
  --model_url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --direct \
  --task "Open WeChat, find the contact named Zhang San, send message: hello"
```

### Python API

```python
import pyautogui
from gui_agents.s3.agents.agent_s import AgentS3
from gui_agents.s3.agents.grounding import DirectACI

engine_params = {
    "engine_type": "openai",
    "model": "kimi-k2.5",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-...",
}

w, h = pyautogui.size()
grounding = DirectACI(env=None, platform="windows", engine_params=engine_params, width=w, height=h)
agent = AgentS3(worker_engine_params=engine_params, grounding_agent=grounding, platform="windows")

agent.reset()
info, code = agent.predict(
    instruction="Open Chrome and go to github.com",
    observation={"screenshot": open("screenshot.png", "rb").read()},
)
exec(code[0])
```

---

## DirectACI Architecture

### How it works

DirectACI is a subclass of `OSWorldACI` that overrides all coordinate-based action methods. Instead of accepting natural-language element descriptions (which are then resolved by a grounding API), DirectACI methods accept `(x, y)` pixel coordinates directly.

```python
# Standard OSWorldACI signature — requires grounding model to resolve description
def click(self, element_description: str, num_clicks: int = 1, button_type: str = "left"):
    ...

# DirectACI signature — model outputs coordinates directly from screenshot
def click(self, x: int, y: int, num_clicks: int = 1, button_type: str = "left"):
    ...
```

The system prompt is auto-generated from method signatures via `inspect.signature()` in `procedural_memory.py`. Changing the signature automatically teaches the model what format to output &mdash; no manual prompt engineering needed.

### Coordinate normalization (`_px`)

Different models output coordinates in different formats. DirectACI normalizes all three:

| Format | Example | Used by |
|--------|---------|---------|
| Float 0&ndash;1 | `(0.472, 0.978)` | kimi-k2.5 |
| Integer 0&ndash;1000 | `(472, 978)` | qwen3.5-plus |
| Absolute pixels | `(906, 1057)` | UI-TARS, manual |

```python
def _px(self, x, y):
    x, y = float(x), float(y)
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:      # float 0-1 (kimi)
        return int(x * self.width), int(y * self.height)
    if x <= 1000 and y <= 1000:                    # int 0-1000 (qwen)
        return int(x * self.width / 1000), int(y * self.height / 1000)
    return int(x), int(y)                          # absolute pixels
```

### Available actions

| Action | DirectACI signature |
|--------|-------------------|
| `click` | `click(x, y, num_clicks, button_type, hold_keys)` |
| `type` | `type(x, y, text, overwrite)` |
| `scroll` | `scroll(x, y, direction, amount)` |
| `drag_and_drop` | `drag_and_drop(start_x, start_y, end_x, end_y)` |
| `key_press` | `key_press(key)` |
| `open_app` | `open_app(app_name)` |
| `done` | `done()` |
| `fail` | `fail(reason)` |

---

## OpenClaw Skill

The `openclaw-skill/` directory contains a ready-to-deploy skill for the OpenClaw platform.

### Install the skill

Copy `openclaw-skill/` to your OpenClaw skills directory and rename it `agent-s-cua`:

```bash
cp -r openclaw-skill/ /path/to/openclaw/skills/agent-s-cua
```

### Invoke from OpenClaw

```
@bot 打开微信，找到联系人"张三"，发送消息：在吗
@bot Open Chrome and log in to github.com
@bot Open Excel, create a sheet named "Sales", enter 1000 in A1
```

### Run directly

```bash
python -X utf8 openclaw-skill/scripts/run_agent_s.py "Open WeChat and send a message"
python -X utf8 openclaw-skill/scripts/run_agent_s.py --max-steps 20 --model qwen3.5-plus "Fill the web form"
```

---

## Models

AutoAct works with any OpenAI-compatible multimodal API. Recommended options:

| Model | Provider | API Endpoint | Best For |
|-------|----------|-------------|---------|
| `kimi-k2.5` | Moonshot / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Default; strong visual reasoning, 256K ctx |
| `qwen-vl-max` | Alibaba DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Larger context (1M), reliable |
| `gpt-4o` | OpenAI | `https://api.openai.com/v1` | Best accuracy, higher cost |
| `claude-opus-4-5` | Anthropic (via OpenRouter) | `https://openrouter.ai/api/v1` | Strong reasoning |

Set your API key as an environment variable:

```bash
# DashScope (Alibaba Cloud — China accessible)
export OPENAI_API_KEY=sk-...

# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic via OpenRouter
export OPENAI_API_KEY=<openrouter_key>
```

---

## CLI Reference

```
agent_s [options] [--task "instruction"]

Core options:
  --provider        API provider type (default: openai)
  --model           Model ID (default: gpt-5-2025-08-07)
  --model_url       Base URL for the API
  --model_api_key   API key (or set via OPENAI_API_KEY env var)

DirectACI (single-model mode):
  --direct          Use one model for both reasoning and grounding
                    (all --ground_* args become optional)

Standard two-model mode (requires separate grounding server):
  --ground_provider   Provider for grounding model
  --ground_url        URL of grounding model server
  --ground_model      Grounding model ID
  --grounding_width   Screenshot width for grounding (px)
  --grounding_height  Screenshot height for grounding (px)

Task options:
  --task            Task instruction (if omitted, enters interactive loop)
  --max_trajectory_length  Max screenshot turns to keep (default: 8)
  --enable_reflection      Enable reflection agent (default: on)

Controls:
  Ctrl+C            Pause execution
  Esc               Resume after pause
  Ctrl+C (x2)       Exit
```

---

## Project Structure

```
Agent-S/
├── gui_agents/
│   └── s3/                        # Production-ready S3 agent
│       ├── agents/
│       │   ├── agent_s.py         # Top-level AgentS3 orchestrator
│       │   ├── grounding.py       # OSWorldACI + DirectACI (our contribution)
│       │   └── worker.py          # Generates GUI actions from observations
│       ├── core/
│       │   ├── engine.py          # LLM provider backends (OpenAI, Anthropic, ...)
│       │   └── mllm.py            # Multimodal message history management
│       └── memory/
│           └── procedural_memory.py  # Auto-generates system prompt from signatures
├── openclaw-skill/                # OpenClaw integration (our contribution)
│   ├── SKILL.md                   # Skill manifest
│   └── scripts/run_agent_s.py    # Standalone runner script
├── examples/                      # Usage examples
└── USAGE.md                       # Full operational guide
```

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

**Areas where help is most useful:**

- Testing DirectACI with more models (Gemini, Claude, Qwen-VL, etc.)
- Improving coordinate accuracy for different screen resolutions
- Additional OpenClaw skill improvements
- macOS / Linux testing
- More example scripts

### Development setup

```bash
git clone https://github.com/jessepwj/Agent-S
cd Agent-S
pip install -e ".[dev]"
black --check gui_agents    # formatting check
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## Credits

AutoAct is built on top of [Agent-S](https://github.com/simular-ai/Agent-S) by [Simular AI](https://simular.ai), which achieved first human-surpassing performance on OSWorld (72.60%).

**Original paper:**
> Simular Research. *Agent S: An Open Agentic Framework that Uses Computers Like a Human.* ICLR 2025.

Contributions in this fork:
- **DirectACI** — single-model coordinate grounding (eliminates separate grounding server)
- **OpenClaw skill** — `agent-s-cua` integration for plug-and-play desktop automation
- Coordinate normalization for kimi-k2.5, qwen3.5-plus, and UI-TARS output formats
- Expanded documentation and operational guides

---

## License

[Apache 2.0](LICENSE) — same as the upstream Agent-S project.
