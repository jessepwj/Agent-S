"""
Example: Send a WeChat message using DirectACI (single-model mode).

Usage:
    export OPENAI_API_KEY=sk-...
    python examples/wechat_demo.py

Or with a custom task:
    python examples/wechat_demo.py "打开微信，找到联系人'李四'，发送消息：下午有空吗"
"""

import io
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pyautogui
from PIL import Image

from gui_agents.s3.agents.agent_s import AgentS3
from gui_agents.s3.agents.grounding import DirectACI

# ---------------------------------------------------------------------------
# Configuration — read from environment variables
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get(
    "OPENAI_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("CLAWUIS_MODEL", "kimi-k2.5")

if not API_KEY:
    print("ERROR: Set the OPENAI_API_KEY environment variable before running.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
TASK = sys.argv[1] if len(sys.argv) > 1 else (
    "打开微信，在联系人列表中找到名为'张三'的联系人，在聊天输入框中输入消息'你好' 并发送"
)

MAX_STEPS = 15

# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------
engine_params = {
    "engine_type": "openai",
    "model": MODEL,
    "base_url": BASE_URL,
    "api_key": API_KEY,
}

screen_width, screen_height = pyautogui.size()

grounding_agent = DirectACI(
    env=None,
    platform="windows",
    engine_params=engine_params,
    width=screen_width,
    height=screen_height,
)

agent = AgentS3(
    worker_engine_params=engine_params,
    grounding_agent=grounding_agent,
    platform="windows",
    max_trajectory_length=8,
    enable_reflection=False,
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
print("=" * 60)
print(f"  Model:  {MODEL}")
print(f"  Task:   {TASK}")
print("=" * 60)

agent.reset()

for step in range(MAX_STEPS):
    shot = pyautogui.screenshot()
    shot = shot.resize((screen_width, screen_height), Image.LANCZOS)
    buf = io.BytesIO()
    shot.save(buf, format="PNG")

    print(f"\n[Step {step + 1}/{MAX_STEPS}] Asking model...")
    info, code = agent.predict(
        instruction=TASK,
        observation={"screenshot": buf.getvalue()},
    )
    action = code[0]
    print(f"[Action] {action[:120]}")

    if "done" in action.lower():
        print(f"\n[DONE] Completed in {step + 1} step(s).")
        break
    if "fail" in action.lower():
        print(f"\n[FAIL] Agent reported failure at step {step + 1}.")
        break
    if "wait" in action.lower():
        print("  Waiting 5s...")
        time.sleep(5)
        continue

    print("  [EXEC]")
    exec(action)  # noqa: S102
    time.sleep(1.5)
else:
    print(f"\n[TIMEOUT] Reached {MAX_STEPS} steps without completion.")
