---
name: agent-s-cua
description: Use when the user needs to perform visual/GUI tasks on the Windows desktop using Agent-S Computer Use Agent — such as opening apps, clicking buttons, filling forms, sending messages in WeChat/DingTalk, navigating websites visually, or any task requiring mouse/keyboard control. Agent-S uses kimi-k2.5 multimodal model to see the screen and operate any application.
read_when:
  - Clicking buttons or UI elements in any app
  - Sending messages in WeChat, DingTalk, or other IM apps
  - Filling web forms or logging into websites visually
  - Operating desktop software (Excel, Chrome, any GUI app)
  - Automating multi-step desktop workflows
  - Any task that needs "someone to use the mouse and keyboard"
metadata: {"clawdbot":{"emoji":"🤖","requires":{"bins":["python"]}}}
---

# Agent-S CUA — Windows Desktop Computer Use Agent

Agent-S S3 takes screenshots, reasons with kimi-k2.5 multimodal model, and executes mouse clicks / keyboard input. Use it when a task cannot be done via CLI or API.

## Quick Usage

Run a task:
```bash
python -X utf8 skills/agent-s-cua/scripts/run_agent_s.py "打开微信，给张三发消息：在吗"
```

With custom max steps (default 15):
```bash
python -X utf8 skills/agent-s-cua/scripts/run_agent_s.py --max-steps 20 "Open Chrome and go to github.com"
```

With a different model:
```bash
python -X utf8 skills/agent-s-cua/scripts/run_agent_s.py --model qwen3.5-plus "Open Notepad and type Hello World"
```

## When to Use

- User says: "帮我打开/点击/填写/发消息/操作..."
- Any task that requires clicking a GUI, not just a terminal command
- Web forms that need real browser login (cookie-based, not API)
- Sending messages in desktop IM apps (WeChat, DingTalk, etc.)

## Task Writing Tips

Be specific. Good examples:
- "打开微信，在联系人列表中找到'张三'，发送消息：你好"
- "Open Chrome, go to https://example.com, click the Login button, enter username and password"
- "Open Excel, create a new sheet named Sales, enter 1000 in cell A1"

Bad (too vague):
- "help me with WeChat" → Agent-S won't know what to do

## Models Available

| Model | Best For |
|-------|---------|
| `kimi-k2.5` (default) | Visual tasks, supports images, 256K context |
| `qwen3.5-plus` | Larger context (1M), also supports images |

## Logs

Monitor progress:
```bash
# Each run creates a timestamped log
cat skills/agent-s-cua/scripts/agent_s_last_run.log
```

## Setup Requirements

- Agent-S S3 project: `E:\aigc研究项目\agent_s3\`（已就绪，无需重新安装）
- API: bailian provider（已在 openclaw.json 中配置）
- Screen resolution: 自动检测
