<h1 align="center">claw-ui-s</h1>

<p align="center">
  <strong>OpenClaw 桌面自动化技能 &mdash; 单模型视觉推理 + 直接执行</strong><br>
  <em>OpenClaw skill for desktop automation &mdash; single-model, no grounding server needed</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/OpenClaw-skill-purple" alt="OpenClaw">
  <img src="https://img.shields.io/badge/model-kimi--k2.5%20%7C%20qwen--vl-orange" alt="Models">
</p>

<p align="center">
  <a href="#中文说明">中文说明</a> &bull;
  <a href="#english">English</a> &bull;
  <a href="#openclaw-skill">OpenClaw Skill</a> &bull;
  <a href="#directaci">DirectACI</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

---

## 中文说明

### 这是什么

claw-ui-s 是基于 [Agent-S](https://github.com/simular-ai/Agent-S) S3 的社区扩展版本，核心贡献有两项：

1. **OpenClaw 技能（`agent-s-cua`）** — 将桌面 GUI 自动化能力打包成 OpenClaw 平台的标准技能，让任何 OpenClaw Bot 都能操控桌面应用。

2. **DirectACI** — 单模型执行模式，用一个多模态大模型（如 kimi-k2.5）同时完成"视觉推理"和"像素坐标输出"，无需再部署独立的 Grounding 服务。

```
原版两步走:  截图 --> 推理模型 --> "点击发送按钮" --> Grounding API --> 坐标 --> pyautogui
DirectACI:  截图 --> kimi-k2.5 ----------------------------------------> 坐标 --> pyautogui
```

### 快速上手

**安装**

```bash
git clone https://github.com/jessepwj/claw-ui-s
cd Agent-S
pip install -e .
```

**设置 API Key**

```bash
# DashScope（阿里云，国内可用）
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**运行任务**

```bash
agent_s \
  --provider openai \
  --model kimi-k2.5 \
  --model_url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --model_api_key $OPENAI_API_KEY \
  --direct \
  --task "打开微信，找到联系人'张三'，发送消息：在吗"
```

**使用 OpenClaw 技能**

将 `openclaw-skill/` 复制到 OpenClaw 技能目录，重命名为 `agent-s-cua`，然后在 Bot 中直接使用：

```
@bot 帮我打开微信，给李四发消息：下午有空吗？
@bot 打开 Chrome，登录 github.com
@bot 打开 Excel，新建 Sheet 命名为"销售数据"，在 A1 填入 1000
```

**直接调用技能脚本**

```bash
python -X utf8 openclaw-skill/scripts/run_agent_s.py "打开微信，给张三发消息：在吗"
python -X utf8 openclaw-skill/scripts/run_agent_s.py --max-steps 20 "填写网页表单"
python -X utf8 openclaw-skill/scripts/run_agent_s.py --model qwen-vl-max "打开记事本"
```

### 支持的模型

| 模型 | 提供方 | 推荐场景 |
|------|--------|----------|
| `kimi-k2.5` | 月之暗面 / DashScope | 默认，视觉理解强，256K 上下文 |
| `qwen-vl-max` | 阿里 DashScope | 超长上下文（1M），稳定 |
| `gpt-4o` | OpenAI | 精度最高，成本较高 |

### DirectACI 原理

DirectACI 继承自原版 `OSWorldACI`，重写了所有含坐标的动作方法。方法签名由 `inspect.signature()` 自动注入系统提示词，所以改变签名就直接改变了模型行为，无需手动写 Prompt。

**坐标自动归一化（`_px`）**：三种格式都支持：

| 格式 | 示例 | 来源模型 |
|------|------|----------|
| 浮点 0–1 | `(0.47, 0.98)` | kimi-k2.5 |
| 整数 0–1000 | `(472, 978)` | qwen3.5-plus |
| 绝对像素 | `(906, 1057)` | UI-TARS |

### 上游项目

claw-ui-s 基于 [Agent-S](https://github.com/simular-ai/Agent-S)（Simular AI），S3 版本在 OSWorld 基准上以 72.60% 首次超越人类表现。

---

## English

### What is claw-ui-s

claw-ui-s is a community-enhanced fork of [Agent-S](https://github.com/simular-ai/Agent-S) S3, adding two contributions:

1. **OpenClaw Skill (`agent-s-cua`)** — packages desktop GUI automation as a standard OpenClaw platform skill, enabling any OpenClaw bot to control desktop applications.

2. **DirectACI** — a single-model execution mode where one multimodal LLM (e.g. kimi-k2.5) handles both visual reasoning and pixel-coordinate output, eliminating the need for a separate grounding model server.

### Quick Start

```bash
git clone https://github.com/jessepwj/claw-ui-s
cd Agent-S
pip install -e .

export OPENAI_API_KEY=sk-...

agent_s \
  --provider openai \
  --model kimi-k2.5 \
  --model_url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --model_api_key $OPENAI_API_KEY \
  --direct \
  --task "Open WeChat, find Zhang San, send: hello"
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
    "api_key": "sk-...",   # or read from os.environ
}

w, h = pyautogui.size()
grounding = DirectACI(env=None, platform="windows", engine_params=engine_params, width=w, height=h)
agent = AgentS3(worker_engine_params=engine_params, grounding_agent=grounding, platform="windows")

agent.reset()
info, code = agent.predict(
    instruction="Open WeChat and send a message",
    observation={"screenshot": open("screen.png", "rb").read()},
)
exec(code[0])
```

---

## OpenClaw Skill

### Installation

```bash
cp -r openclaw-skill/ /path/to/openclaw/skills/agent-s-cua
```

### Usage in OpenClaw

```
@bot 打开微信，找到"张三"，发消息：在吗
@bot Open Chrome and go to github.com
@bot Open Excel and create a sheet named Sales
```

### Direct invocation

```bash
# Set env vars first
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

python -X utf8 openclaw-skill/scripts/run_agent_s.py "your task here"
```

---

## DirectACI

### Architecture

```
Standard (two-model):
  Screenshot -> Reasoning LLM -> "click Send button" -> Grounding API -> (x,y) -> pyautogui

DirectACI (one-model):
  Screenshot -> kimi-k2.5 -----------------------------------------> (x,y) -> pyautogui
```

### Action signatures

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

### Coordinate normalization

```python
def _px(self, x, y):
    x, y = float(x), float(y)
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:   # kimi: float 0-1
        return int(x * self.width), int(y * self.height)
    if x <= 1000 and y <= 1000:                 # qwen: int 0-1000
        return int(x * self.width / 1000), int(y * self.height / 1000)
    return int(x), int(y)                       # absolute pixels
```

---

## CLI Reference

```
agent_s --provider openai --model <model> --model_url <url> --model_api_key <key>
        --direct
        --task "instruction"

Key flags:
  --direct          Single-model mode (no grounding server required)
  --task            Task to run (omit for interactive loop)
  --enable_reflection  Reflection agent on/off (default: on)
  --max_trajectory_length  History window (default: 8 screenshots)

Keyboard shortcuts (during execution):
  Ctrl+C            Pause
  Esc               Resume
  Ctrl+C twice      Exit
```

---

## Project Structure

```
Agent-S/
├── gui_agents/s3/
│   ├── agents/grounding.py     # DirectACI (this project's contribution)
│   ├── agents/agent_s.py       # AgentS3 orchestrator (upstream)
│   └── agents/worker.py        # Action generation (upstream)
├── openclaw-skill/             # OpenClaw skill (this project's contribution)
│   ├── SKILL.md                # Skill manifest
│   └── scripts/run_agent_s.py # Standalone runner
├── examples/
│   └── wechat_demo.py         # Example script
└── USAGE.md                   # Full operational guide (CN)
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Key areas:

- Test DirectACI with more models and report coordinate formats
- macOS / Linux compatibility testing
- OpenClaw skill improvements and new invocation patterns
- More example scripts

---

## Credits

Built on [Agent-S](https://github.com/simular-ai/Agent-S) by [Simular AI](https://simular.ai) — first to surpass human performance on OSWorld (72.60%).

Contributions in this fork:
- **DirectACI** — single-model grounding, no separate API
- **OpenClaw skill** (`agent-s-cua`) — plug-and-play desktop automation for OpenClaw
- Coordinate normalization for kimi-k2.5 / qwen / UI-TARS output formats

---

## License

[Apache 2.0](LICENSE)
