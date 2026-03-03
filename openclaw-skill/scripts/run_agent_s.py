"""
Agent-S CUA — Windows Desktop Computer Use Agent
Uses Agent-S S3 + kimi-k2.5 (via bailian) for visual desktop automation.

Usage:
    python -X utf8 run_agent_s.py "打开微信，给张三发消息：在吗"
    python -X utf8 run_agent_s.py --max-steps 20 "Open Chrome and search for cats"
    python -X utf8 run_agent_s.py --model qwen3.5-plus "Open Notepad"
"""

import argparse
import io
import os
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 工作目录修正 — 使用 E:\aigc内容整理\Agent-S (含 DirectACI)
# 路径含中文，用字节编码绕过 Windows 路径限制
# ---------------------------------------------------------------------------
def _find_agent_s_root() -> Path | None:
    """查找包含 DirectACI 的 Agent-S 项目根目录。"""
    # 优先使用已知包含 DirectACI 的 Agent-S 目录
    _candidates = [
        Path("E:/aigc\u5185\u5bb9\u6574\u7406/Agent-S"),  # E:\aigc内容整理\Agent-S
        Path("E:/aigc\u7814\u7a76\u9879\u76ee/Agent-S"),   # E:\aigc研究项目\Agent-S
        Path.home() / "Agent-S",
    ]
    for _p in _candidates:
        if (_p / "gui_agents").exists() and (_p / "run_direct_task.py").exists():
            return _p
    # 备用：从 sys.path 中查找含 DirectACI 的 gui_agents
    import importlib.util
    spec = importlib.util.find_spec("gui_agents")
    if spec and spec.origin:
        root = Path(spec.origin).parent.parent
        grounding = root / "gui_agents" / "s3" / "agents" / "grounding.py"
        if grounding.exists() and "DirectACI" in grounding.read_text(encoding="utf-8", errors="replace"):
            return root
    return None

AGENT_S_ROOT = _find_agent_s_root()
if AGENT_S_ROOT and AGENT_S_ROOT.exists():
    os.chdir(AGENT_S_ROOT)
    root_str = str(AGENT_S_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    print(f"[INFO] Agent-S root: {root_str}", file=sys.stderr)
else:
    print("[WARN] Cannot locate Agent-S root with DirectACI. Import may fail.", file=sys.stderr)

# ---------------------------------------------------------------------------
# Config — mirrors openclaw.json bailian provider
# ---------------------------------------------------------------------------
BASE_URL  = "https://coding.dashscope.aliyuncs.com/v1"
API_KEY   = "REDACTED"
DEFAULT_MODEL    = "kimi-k2.5"
DEFAULT_MAX_STEPS = 15

LOG_FILE = Path(__file__).parent / "agent_s_last_run.log"


def parse_args():
    parser = argparse.ArgumentParser(description="Agent-S CUA for Windows")
    parser.add_argument("task", nargs="?", help="Task instruction in natural language")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                        help=f"Max execution steps (default: {DEFAULT_MAX_STEPS})")
    parser.add_argument("--no-reflection", action="store_true",
                        help="Disable reflection (faster, fewer API calls)")
    return parser.parse_args()


def build_engine_params(model: str) -> dict:
    return {
        "engine_type": "openai",
        "model": model,
        "base_url": BASE_URL,
        "api_key": API_KEY,
    }


def run_task(instruction: str, model: str, max_steps: int, enable_reflection: bool):
    try:
        import pyautogui
        from PIL import Image
    except ImportError as e:
        print(f"[ERROR] {e} — 请在 Agent-S 项目环境下运行本脚本")
        sys.exit(1)

    try:
        from gui_agents.s3.agents.agent_s import AgentS3
        from gui_agents.s3.agents.grounding import DirectACI
    except ImportError as e:
        print(f"[ERROR] {e} — gui_agents 未找到，当前 Agent-S root: {AGENT_S_ROOT}")
        sys.exit(1)

    screen_width, screen_height = pyautogui.size()
    engine_params = build_engine_params(model)

    print(f"  Screen: {screen_width}x{screen_height}")
    print(f"  Model:  {model}")
    print(f"  Steps:  max {max_steps}")
    print(f"  Task:   {instruction}")
    print("-" * 60)

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
        enable_reflection=enable_reflection,
    )

    agent.reset()
    result = "UNKNOWN"

    for step in range(max_steps):
        shot = pyautogui.screenshot()
        shot = shot.resize((screen_width, screen_height), Image.LANCZOS)
        buf = io.BytesIO()
        shot.save(buf, format="PNG")

        print(f"\n[Step {step + 1}/{max_steps}] Asking model...")
        try:
            info, code = agent.predict(
                instruction=instruction,
                observation={"screenshot": buf.getvalue()},
            )
        except Exception as exc:
            print(f"[ERROR] Model call failed at step {step + 1}: {exc}")
            traceback.print_exc()
            result = "ERROR"
            break

        action = code[0] if code else "done"
        action_preview = action[:120].replace("\n", " ")
        print(f"[Action] {action_preview}")

        action_lower = action.lower()
        if "done" in action_lower:
            print(f"\n[DONE] Task completed in {step + 1} step(s).")
            result = "DONE"
            break
        if "fail" in action_lower:
            print(f"\n[FAIL] Agent reported failure at step {step + 1}.")
            result = "FAIL"
            break

        if "wait" in action_lower:
            print("  [WAIT] Sleeping 5s...")
            time.sleep(5)
            continue

        print("  [EXEC]")
        try:
            exec(action)  # noqa: S102
        except Exception as exc:
            print(f"  [EXEC ERROR] {exc}")

        time.sleep(1.5)
    else:
        print(f"\n[TIMEOUT] Reached max steps ({max_steps}) without completion.")
        result = "TIMEOUT"

    return result


def main():
    args = parse_args()

    if not args.task:
        print("Usage: python run_agent_s.py \"your task here\"")
        print("Example: python run_agent_s.py \"打开微信，给张三发消息：在吗\"")
        sys.exit(1)

    instruction = args.task
    model = args.model
    max_steps = args.max_steps
    enable_reflection = not args.no_reflection

    print("=" * 60)
    print("  Agent-S CUA — Windows Desktop Automation")
    print("=" * 60)

    start = time.time()
    result = "ERROR"
    try:
        result = run_task(instruction, model, max_steps, enable_reflection)
    except KeyboardInterrupt:
        print("\n[STOPPED] User interrupted.")
        result = "STOPPED"
    except Exception as exc:
        print(f"\n[FATAL] {exc}")
        traceback.print_exc()
        result = "ERROR"
    finally:
        elapsed = time.time() - start
        summary = (
            f"Result: {result} | "
            f"Model: {model} | "
            f"Elapsed: {elapsed:.1f}s | "
            f"Task: {instruction}"
        )
        print(f"\n{'=' * 60}")
        print(f"  {summary}")
        print("=" * 60)

        try:
            LOG_FILE.write_text(summary + "\n", encoding="utf-8")
        except Exception:
            pass

    sys.exit(0 if result == "DONE" else 1)


if __name__ == "__main__":
    main()
