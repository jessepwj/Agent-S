# Agent-S 使用手册

本文档记录使用 Agent-S S3 的完整流程、踩过的坑及修复方案。

---

## 版本说明

| 版本 | 目录 | 特点 |
|------|------|------|
| S1 | `gui_agents/s1/` | 原版，ICLR 2025 Best Paper |
| S2 | `gui_agents/s2/` | 层级式架构 |
| S2.5 | `gui_agents/s2_5/` | S2 简化版 |
| **S3** | `gui_agents/s3/` | **当前最新，推荐使用** |

---

## 安装

```bash
# 从 PyPI 安装
pip install gui-agents

# 或本地开发模式（克隆后）
pip install -e .
```

---

## 架构说明：为什么需要两个模型

Agent-S 把任务拆成两步，分给两个模型：

```
主模型（Worker）
  接收：截图 + 任务描述 + 历史操作
  输出：agent.click("微信图标")  ← 自然语言描述，不是坐标

        ↓

Grounding 模型
  接收：截图 + "微信图标"
  输出：(906, 1049)  ← 像素坐标

        ↓

pyautogui.click(906, 1049)  ← 真正执行
```

**可以用同一个模型兼任两个角色**（见下方启动命令），只要该模型支持图片输入即可。

---

## 推荐模型配置（无需本地部署）

使用阿里云百炼平台，两个模型都支持图片输入，可兼任主模型 + Grounding 模型。

| 模型 | 特点 |
|------|------|
| `qwen3.5-plus` | 速度快，视觉理解强，任务完成率高 |
| `kimi-k2.5` | 界面分析细致，操作步骤更谨慎 |

**API 配置：**

```
Base URL : https://coding.dashscope.aliyuncs.com/v1
API Key  : （填写你的 key）
```

---

## 启动命令

### 用 kimi-k2.5（推荐）

```bash
agent_s \
  --provider openai \
  --model kimi-k2.5 \
  --model_url https://coding.dashscope.aliyuncs.com/v1 \
  --model_api_key <YOUR_KEY> \
  --ground_provider openai \
  --ground_model kimi-k2.5 \
  --ground_url https://coding.dashscope.aliyuncs.com/v1 \
  --ground_api_key <YOUR_KEY> \
  --grounding_width 1920 \
  --grounding_height 1080
```

### 用 qwen3.5-plus

```bash
agent_s \
  --provider openai \
  --model qwen3.5-plus \
  --model_url https://coding.dashscope.aliyuncs.com/v1 \
  --model_api_key <YOUR_KEY> \
  --ground_provider openai \
  --ground_model qwen3.5-plus \
  --ground_url https://coding.dashscope.aliyuncs.com/v1 \
  --ground_api_key <YOUR_KEY> \
  --grounding_width 1920 \
  --grounding_height 1080
```

### Python SDK 方式

```python
import io, pyautogui
from PIL import Image
from gui_agents.s3.agents.agent_s import AgentS3
from gui_agents.s3.agents.grounding import OSWorldACI

BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
API_KEY  = "<YOUR_KEY>"
MODEL    = "kimi-k2.5"   # 或 "qwen3.5-plus"

engine_params = {
    "engine_type": "openai",
    "model": MODEL,
    "base_url": BASE_URL,
    "api_key": API_KEY,
}
engine_params_grounding = {
    **engine_params,
    "grounding_width": 1920,
    "grounding_height": 1080,
}

grounding_agent = OSWorldACI(
    env=None,
    platform="windows",          # "darwin" / "linux"
    engine_params_for_generation=engine_params,
    engine_params_for_grounding=engine_params_grounding,
    width=1920,
    height=1080,
)

agent = AgentS3(
    worker_engine_params=engine_params,
    grounding_agent=grounding_agent,
    platform="windows",
    max_trajectory_length=8,
    enable_reflection=False,
)

# 运行一个任务（循环到 DONE/FAIL）
INSTRUCTION = "打开微信，给敏敏敏发消息：爱你哟"

for step in range(15):
    shot = pyautogui.screenshot()
    shot = shot.resize((1920, 1080), Image.LANCZOS)
    buf = io.BytesIO()
    shot.save(buf, format="PNG")

    info, code = agent.predict(
        instruction=INSTRUCTION,
        observation={"screenshot": buf.getvalue()}
    )
    action = code[0]
    print(f"[Step {step+1}] {action}")

    if "done" in action.lower() or "fail" in action.lower():
        break

    exec(action)

    import time; time.sleep(1.5)
```

---

## 操作控制

| 操作 | 效果 |
|------|------|
| `Ctrl+C` | 暂停（再按 Esc 继续） |
| `Ctrl+C` 两次 | 退出 |

---

## 已知 Bug 及修复记录

### Bug 1：Grounding 坐标解析错误（已修复，commit `0477359`）

**文件**：`gui_agents/s3/agents/grounding.py`，`generate_coords()` 方法

**问题**：

kimi-k2.5、qwen3.5-plus 等模型返回**归一化浮点坐标**（0~1 范围），例如：

```
模型输出: (0.472, 0.979)
```

原代码用 `re.findall(r"\d+", response)` 只取整数部分，解析结果变成 `(0, 472)`，导致点击位置完全错误。

**修复**（`grounding.py` 第 240 行附近）：

```python
# 修复前（只支持整数格式）
numericals = re.findall(r"\d+", response)
assert len(numericals) >= 2
return [int(numericals[0]), int(numericals[1])]

# 修复后（同时支持归一化浮点 + 绝对像素整数）
floats = re.findall(r"\d+\.\d+", response)
if len(floats) >= 2:
    fx, fy = float(floats[0]), float(floats[1])
    if 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0:
        return [int(fx * self.width), int(fy * self.height)]
    return [int(fx), int(fy)]
numericals = re.findall(r"\d+", response)
assert len(numericals) >= 2
return [int(numericals[0]), int(numericals[1])]
```

---

## 常见问题

### Q：启动报 `TesseractNotFoundError`

OCR 功能不可用，但不影响视觉坐标定位。如需完整功能，安装 Tesseract：

- 下载：https://github.com/UB-Mannheim/tesseract/wiki
- 安装后将 `tesseract.exe` 所在路径加入系统 PATH

### Q：官方推荐的 UI-TARS Grounding 模型怎么用

UI-TARS 是专门为 GUI 坐标定位训练的模型，精度高于通用模型，但需要自行部署：

```bash
# 本地部署需约 16GB 显存，使用 vLLM 或 HuggingFace TGI
# 部署后将 ground_url 指向服务地址即可
agent_s ... --ground_model ui-tars-1.5-7b --ground_url http://localhost:8080
```

### Q：只有单显示器才能用

Agent-S 仅支持单显示器，多屏环境下截图和坐标会出问题。

### Q：任务执行时模型调用了几次 API

每个需要点击的步骤会调用 **2次** API：
1. 主模型决策（输出 `agent.click("描述")`）
2. Grounding 模型定位（输出坐标）

纯键盘操作（`hotkey`、`type`）只调用 1次。
