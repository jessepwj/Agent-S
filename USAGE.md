# Agent-S 完整使用手册

> 本文档记录 Agent-S S3 从零搭建到实际跑通的全部经验：架构原理、模型配置、启动方式、踩过的所有坑、修复方案及代码改动说明。

---

## 目录

1. [项目简介](#1-项目简介)
2. [版本说明](#2-版本说明)
3. [安装](#3-安装)
4. [架构原理](#4-架构原理)
5. [模型选择与配置](#5-模型选择与配置)
6. [启动方式](#6-启动方式)
7. [Python SDK 用法](#7-python-sdk-用法)
8. [操作控制](#8-操作控制)
9. [Bug 记录与修复](#9-bug-记录与修复)
10. [各模型实测对比](#10-各模型实测对比)
11. [常见问题](#11-常见问题)
12. [关键代码位置速查](#12-关键代码速查)

---

## 1 项目简介

Agent-S 是一个多模态 LLM 驱动的 GUI 自动化框架，让 AI 像人一样操作电脑桌面：看截图、分析界面、生成鼠标/键盘动作并执行。

- 论文：ICLR 2025 Best Paper（S1 版）
- S3 版在 OSWorld 基准达到 **72.60%**，首次超越人类水平
- PyPI 包名：`gui-agents`
- GitHub：https://github.com/simular-ai/Agent-S

---

## 2 版本说明

| 版本 | 目录 | 特点 |
|------|------|------|
| S1 | `gui_agents/s1/` | 原版，ICLR 2025 Best Paper，基于知识检索 |
| S2 | `gui_agents/s2/` | 层级式 specialist-generalist 架构，COLM 2025 |
| S2.5 | `gui_agents/s2_5/` | S2 的简化版 |
| **S3** | `gui_agents/s3/` | **当前最新，推荐使用**，扁平架构，推理最快 |

所有新功能开发都在 `gui_agents/s3/` 里进行。

---

## 3 安装

```bash
# 从 PyPI 安装（稳定版）
pip install gui-agents

# 本地开发模式（克隆仓库后）
git clone https://github.com/simular-ai/Agent-S.git
cd Agent-S
pip install -e ".[dev]"
```

**Windows 额外依赖**（用于控制桌面）：

```bash
pip install pyautogui pyperclip pillow
# 如果需要窗口管理
pip install pywinauto pywin32
```

---

## 4 架构原理

### 4.1 S3 核心组件

| 文件 | 作用 |
|------|------|
| `s3/cli_app.py` | CLI 入口，截图循环，Ctrl+C 暂停 |
| `s3/agents/agent_s.py` | AgentS3 顶层编排，组合 Worker + Reflection |
| `s3/agents/worker.py` | 生成下一步动作，调用 LMM，管理对话历史 |
| `s3/agents/grounding.py` | ACI / OSWorldACI / DirectACI，把抽象动作转成 pyautogui 代码 |
| `s3/core/mllm.py` | LMMAgent，统一多模态 LLM 封装 |
| `s3/core/engine.py` | 各 provider 的 LLM engine 实现 |
| `s3/memory/procedural_memory.py` | 系统提示词构造（方法签名自动注入） |
| `s3/utils/local_env.py` | LocalEnv，沙箱代码执行，30秒超时 |

### 4.2 经典双模型模式

原始设计把一个步骤拆成两次 API 调用：

```
截图
  |
  v
Worker 模型（主模型）
  输入：截图 + 任务 + 历史操作
  输出：agent.click("微信图标")   <- 自然语言描述，不含坐标

  |  (第二次 API 调用)
  v

Grounding 模型（定位模型）
  输入：截图 + "微信图标"
  输出：(906, 1049)              <- 像素坐标

  |
  v

pyautogui.click(906, 1049)      <- 真正执行鼠标点击
```

**设计原因**：分离"思考做什么"和"看哪个位置"，Grounding 模型可以换成专门的视觉定位模型（如 UI-TARS），精度更高。

### 4.3 单模型直出模式（--direct，推荐）

强推理模型（kimi-k2.5 等）同时具备分析和视觉定位能力，可以一步完成，**省去第二次 API 调用**：

```
截图
  |
  v
kimi-k2.5（单模型）
  输入：截图 + 任务 + 历史操作
  输出：agent.click(0.472, 0.978)  <- 直接给出归一化坐标

  |  (DirectACI._px() 自动转换)
  v

pyautogui.click(906, 1057)         <- 转换为真实像素后执行
```

启动只需加 `--direct` 参数，无需任何 Grounding 模型配置。

### 4.4 系统提示词自动生成机制

Worker 的系统提示词里的"可用方法列表"不是手写的，而是从 ACI 类的方法签名 + docstring **自动生成**：

```python
# procedural_memory.py
for attr_name in dir(agent_class):
    attr = getattr(agent_class, attr_name)
    if callable(attr) and hasattr(attr, 'is_agent_action'):
        signature = inspect.signature(attr)
        procedural_memory += f"def {attr_name}{signature}:\n'''{attr.__doc__}'''"
```

所以 DirectACI 重写了 `click(x, y)` 签名后，模型自动学会输出坐标格式，**不需要手动改提示词**。

---

## 5 模型选择与配置

### 5.1 推荐：阿里云百炼平台（无需本地部署）

两个模型均支持图片输入，可直接接入，不需要 GPU。

| 模型 | 特点 | 推荐场景 |
|------|------|---------|
| `kimi-k2.5` | 推理细致，界面分析准确，坐标输出稳定 | --direct 单模型主力 |
| `qwen3.5-plus` | 速度快，任务理解强 | 双模型主模型（推理侧） |

**API 接入配置**：

```
Base URL : https://coding.dashscope.aliyuncs.com/v1
API Key  : sk-sp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Provider : openai  （用 OpenAI 兼容接口）
```

### 5.2 坐标输出格式（各模型差异）

这是最重要的实测发现，不同模型输出坐标的格式完全不同：

| 模型 | 坐标格式 | 示例输出 | 换算方式 |
|------|---------|---------|---------|
| kimi-k2.5 | 归一化浮点 0.0~1.0 | `(0.472, 0.979)` | x_px = 0.472 * 1920 = 906 |
| qwen3.5-plus | 归一化整数 0~1000 | `[467, 983]` | x_px = 467 * 1920 / 1000 = 896 |
| UI-TARS | 绝对像素 | `(906, 1061)` | 直接用，无需换算 |

修复后的代码（`generate_coords()` 和 `DirectACI._px()`）已自动识别三种格式：

```python
def _px(self, x, y):
    x, y = float(x), float(y)
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:       # kimi 格式
        return int(x * self.width), int(y * self.height)
    if x <= 1000 and y <= 1000:                     # qwen 格式
        return int(x * self.width / 1000), int(y * self.height / 1000)
    return int(x), int(y)                           # UI-TARS 格式
```

### 5.3 官方推荐的 UI-TARS（需自行部署）

UI-TARS 是专门为 GUI 坐标定位训练的视觉模型，精度高于通用 LLM：

| 型号 | 显存需求 | 推荐分辨率 |
|------|---------|----------|
| UI-TARS-1.5-7B | ~16GB | 1920x1080 |
| UI-TARS-72B | ~160GB | 1000x1000 |

```bash
# 用 vLLM 部署（需要 NVIDIA GPU）
vllm serve bytedance-research/UI-TARS-1.5-7B --port 8080

# 然后接入 Agent-S
agent_s \
  --provider openai --model gpt-4o ... \
  --ground_provider huggingface \
  --ground_url http://localhost:8080 \
  --ground_model ui-tars-1.5-7b \
  --grounding_width 1920 --grounding_height 1080
```

---

## 6 启动方式

### 6.1 单模型直出模式（推荐）

最简配置，每步只调用一次 API：

```bash
agent_s \
  --direct \
  --provider openai \
  --model kimi-k2.5 \
  --model_url https://coding.dashscope.aliyuncs.com/v1 \
  --model_api_key <YOUR_KEY>
```

指定任务直接运行（不进入交互模式）：

```bash
agent_s \
  --direct \
  --provider openai \
  --model kimi-k2.5 \
  --model_url https://coding.dashscope.aliyuncs.com/v1 \
  --model_api_key <YOUR_KEY> \
  --task "打开微信，给张三发消息：在吗"
```

### 6.2 双模型模式（kimi-k2.5 兼任两个角色）

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

### 6.3 双模型模式（qwen3.5-plus 主模型 + kimi-k2.5 定位）

主模型做推理（文字），kimi 做定位（图片），分工明确：

```bash
agent_s \
  --provider openai \
  --model qwen3.5-plus \
  --model_url https://coding.dashscope.aliyuncs.com/v1 \
  --model_api_key <YOUR_KEY> \
  --ground_provider openai \
  --ground_model kimi-k2.5 \
  --ground_url https://coding.dashscope.aliyuncs.com/v1 \
  --ground_api_key <YOUR_KEY> \
  --grounding_width 1920 \
  --grounding_height 1080
```

### 6.4 Windows 启动注意事项

Windows 下编码问题需要加 `-X utf8`：

```bash
python -X utf8 -m gui_agents.s3.cli_app --direct ...
```

或者在脚本开头加：

```python
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

---

## 7 Python SDK 用法

### 7.1 单模型直出（推荐）

```python
import io
import sys
import time
import pyautogui
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gui_agents.s3.agents.agent_s import AgentS3
from gui_agents.s3.agents.grounding import DirectACI

BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
API_KEY  = "sk-sp-xxxxxxxxxxxxxxxx"
MODEL    = "kimi-k2.5"

engine_params = {
    "engine_type": "openai",
    "model": MODEL,
    "base_url": BASE_URL,
    "api_key": API_KEY,
}

screen_width, screen_height = pyautogui.size()

grounding_agent = DirectACI(
    env=None,
    platform="windows",    # "darwin" / "linux"
    engine_params=engine_params,
    width=screen_width,
    height=screen_height,
)

agent = AgentS3(
    worker_engine_params=engine_params,
    grounding_agent=grounding_agent,
    platform="windows",
    max_trajectory_length=8,
    enable_reflection=False,   # False 时少一次 API 调用，速度更快
)

INSTRUCTION = "打开微信，给敏敏敏发消息：爱你哟"

agent.reset()

for step in range(15):
    shot = pyautogui.screenshot()
    shot = shot.resize((screen_width, screen_height), Image.LANCZOS)
    buf = io.BytesIO()
    shot.save(buf, format="PNG")

    info, code = agent.predict(
        instruction=INSTRUCTION,
        observation={"screenshot": buf.getvalue()},
    )
    action = code[0]
    print(f"[Step {step+1}] {action[:100]}")

    if "done" in action.lower() or "fail" in action.lower():
        break

    exec(action)
    time.sleep(1.5)
```

### 7.2 双模型模式

```python
from gui_agents.s3.agents.grounding import OSWorldACI

engine_params = {
    "engine_type": "openai",
    "model": "kimi-k2.5",
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": API_KEY,
}
engine_params_grounding = {
    **engine_params,
    "grounding_width": 1920,
    "grounding_height": 1080,
}

grounding_agent = OSWorldACI(
    env=None,
    platform="windows",
    engine_params_for_generation=engine_params,
    engine_params_for_grounding=engine_params_grounding,
    width=1920,
    height=1080,
)
```

---

## 8 操作控制

| 快捷键 | 效果 |
|-------|------|
| `Ctrl+C` | 暂停 Agent，出现菜单 |
| `Esc`（暂停后） | 继续执行 |
| `Ctrl+C`（暂停后） | 完全退出 |

**后台运行时终止进程**（Windows）：

```bash
# 查找进程
wmic process where "commandline like '%run_task%'" get processid,commandline

# 终止进程
taskkill /PID <PID> /F
```

---

## 9 Bug 记录与修复

### Bug 1：Grounding 坐标解析——小数点被截断（commit `0477359`）

**文件**：`gui_agents/s3/agents/grounding.py`，`generate_coords()` 方法

**现象**：点击位置完全错误，坐标偏到屏幕左上角

**根本原因**：

```python
# 原代码——只匹配整数
numericals = re.findall(r"\d+", response)
# kimi 返回 "(0.472,0.979)"
# re.findall 结果 = ['0', '472', '0', '979']
# 取前两个 → (0, 472)  完全错误！
```

**修复**：

```python
# 先检查浮点数
floats = re.findall(r"\d+\.\d+", response)
if len(floats) >= 2:
    fx, fy = float(floats[0]), float(floats[1])
    if 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0:
        return [int(fx * self.width), int(fy * self.height)]
    return [int(fx), int(fy)]
# 再处理整数
numericals = re.findall(r"\d+", response)
...
```

---

### Bug 2：qwen3.5-plus 使用 0-1000 整数坐标（commit `d9ced0a`，用户提交）

**文件**：`gui_agents/s3/agents/grounding.py`，`generate_coords()` 方法

**现象**：用 qwen 定位时坐标偏到屏幕中间

**根本原因**：

qwen3.5-plus 输出 `[467, 983]`，代码把这当成绝对像素直接用，但它实际是 0-1000 范围的归一化值：
- `467 / 1000 * 1920 = 896` 才是真实 x 坐标
- 直接用 `467` 作为 x 坐标则点到了屏幕左半部分

**修复**：

```python
ix, iy = int(numericals[0]), int(numericals[1])
if ix <= 1000 and iy <= 1000:
    # 0-1000 归一化格式（qwen）
    return [int(ix * self.width / 1000), int(iy * self.height / 1000)]
# 绝对像素格式（UI-TARS 等）
return [ix, iy]
```

---

### Bug 3：kimi-k2.5 偶尔输出推理文字而非坐标（commit `d9ced0a`，用户提交）

**文件**：`gui_agents/s3/agents/grounding.py`，`generate_coords()` 方法

**现象**：某些步骤 Grounding 调用失败，返回一长段中文推理文字

**根本原因**：kimi-k2.5 是推理模型，有时会先输出思考过程再给坐标，导致解析失败

**修复**：检测到长文本（>120字符且数字少于4个）时，用更强的约束重问一遍：

```python
for attempt in range(2):
    response = call_llm_safe(self.grounding_model)
    nums_found = re.findall(r"\d+\.?\d*", response)
    if len(nums_found) < 2 or (len(response) > 120 and len(nums_found) < 4):
        if attempt == 0:
            self.grounding_model.reset()
            retry_prompt = (
                f"Query:{ref_expr}\n"
                "Reply with ONLY two numbers separated by a comma, "
                "representing the x and y coordinate. No other text."
            )
            self.grounding_model.add_message(...)
            continue
    break
```

---

### Bug 4：DirectACI 单模型模式坐标未换算（commit `c681b7e`）

**文件**：`gui_agents/s3/agents/grounding.py`，`DirectACI` 类

**现象**：`--direct` 模式下触发 `pyautogui.FailSafeException`，鼠标飞到屏幕角落

**根本原因**：

kimi-k2.5 在 `--direct` 模式下依然输出归一化浮点坐标 `(0.472, 0.978)`，DirectACI 直接把这个值传给 `pyautogui.click(0.472, 0.978)`，pyautogui 把小于 1 的值当成接近原点的位置，触发 fail-safe。

**修复**：在 DirectACI 里加 `_px()` 坐标归一化方法：

```python
def _px(self, x, y):
    """自动识别坐标格式并转换为真实像素"""
    x, y = float(x), float(y)
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:    # kimi: 归一化浮点
        return int(x * self.width), int(y * self.height)
    if x <= 1000 and y <= 1000:                  # qwen: 0-1000 整数
        return int(x * self.width / 1000), int(y * self.height / 1000)
    return int(x), int(y)                        # UI-TARS: 绝对像素
```

所有涉及坐标的方法（`click`、`type`、`scroll`、`drag_and_drop`、`highlight_text_span`）都调用 `_px()` 转换。

---

### Bug 5：Windows 控制台 GBK 编码报错

**现象**：模型返回 emoji 或特殊字符时，`print()` 抛出 `UnicodeEncodeError: 'gbk' codec can't encode`

**修复**：脚本开头加：

```python
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

或运行时加参数：

```bash
python -X utf8 your_script.py
```

---

### Bug 6：qwen3.5-plus 大图片 API 超时

**现象**：qwen 作为 Grounding 模型时，发送 PNG 截图后 20+ 秒超时，报 `InternalServerError: stream timeout`

**根本原因**：`coding.dashscope.aliyuncs.com` 这个 endpoint 针对代码任务优化，处理大图片（>50KB PNG）能力有限

**解决方案**：
1. 用 `--direct` 模式，qwen 只处理文字推理，不再处理大图片
2. 或把 Grounding 换成 kimi-k2.5（对大图片无此问题）
3. 截图用 JPEG 格式压缩后发送

---

## 10 各模型实测对比

### 测试任务

> 打开微信，在联系人列表中找到名为"敏敏敏"的联系人，在聊天输入框中输入消息"爱你哟"并发送

### 结果对比

| 模式 | 主模型 | Grounding 模型 | 步数 | 结果 |
|------|-------|----------------|------|------|
| 双模型 | kimi-k2.5 | kimi-k2.5 | 10步 | DONE |
| 单模型 --direct | kimi-k2.5 | 无 | **7步** | DONE |
| 双模型 | qwen3.5-plus | qwen3.5-plus | 中断 | -- |

### 单模型模式实际执行步骤（7步完成）

```
Step 1: click(902, 1064)   <- 点击任务栏微信图标，打开微信
Step 2: click(435, 114)    <- 点击搜索框
Step 3: type(text="敏敏敏") <- 输入联系人名
Step 4: click(468, 195)    <- 选中搜索结果中的联系人
Step 5: type(text="爱你哟") <- 在聊天框输入消息
Step 6: click(1224, 945)   <- 点击发送按钮
Step 7: DONE
```

### 结论

- **--direct 单模型模式效率更高**：省去每步的 Grounding API 调用，同样任务步数更少
- kimi-k2.5 同时具备推理和视觉定位能力，单模型可以胜任
- qwen3.5-plus 更适合作为纯推理主模型，不适合做 Grounding（大图超时问题）

---

## 11 常见问题

### Q：启动报 `TesseractNotFoundError`

OCR 功能（用于文字选取高亮）依赖 Tesseract，但基本的视觉点击用不到它。

安装方法（Windows）：
1. 下载：https://github.com/UB-Mannheim/tesseract/wiki
2. 安装后把 `C:\Program Files\Tesseract-OCR` 加入系统 PATH
3. 重开终端验证：`tesseract --version`

### Q：单显示器限制

Agent-S 仅支持单主显示器。多屏环境下 `pyautogui.screenshot()` 只截主屏，但鼠标坐标可能受扩展屏影响导致偏移。建议单屏运行或禁用副屏。

### Q：DPI 缩放问题

Windows 开启了 DPI 缩放（如 125%、150%）时，pyautogui 的坐标与截图坐标可能不一致。

检查方法：

```python
import pyautogui
w, h = pyautogui.size()
print(f"pyautogui 分辨率: {w}x{h}")
# 如果这个值和实际分辨率不同，说明存在 DPI 缩放

from PIL import Image
shot = pyautogui.screenshot()
print(f"截图分辨率: {shot.size}")
```

如果两个值相同（本机测试结果一致），无需处理。

### Q：每步调用几次 API

| 模式 | 点击/滚动/拖拽 | 纯键盘操作（hotkey/type） |
|------|--------------|------------------------|
| --direct 单模型 | 1次 | 1次 |
| 双模型 | 2次（主+Grounding） | 1次（仅主） |

enable_reflection=True 时每步额外多 1次（Reflection 模型）。

### Q：如何扩展支持新的动作

在 `grounding.py` 的 ACI 子类里加方法，加 `@agent_action` 装饰器，系统提示词会自动更新：

```python
@agent_action
def right_click(self, x: int, y: int):
    """Right-click at coordinate.
    Args:
        x:int, x pixel coordinate
        y:int, y pixel coordinate
    """
    px, py = self._px(x, y)
    return f"import pyautogui; pyautogui.rightClick({px}, {py})"
```

### Q：反射模式（enable_reflection）有什么用

开启后每步额外调用一次 Reflection 模型，分析轨迹是否在循环或卡住，给 Worker 提供反馈。

- 优点：减少无效循环，任务成功率更高
- 缺点：每步多 1次 API 调用，速度更慢
- 建议：短任务关闭（`enable_reflection=False`），复杂任务开启

### Q：max_trajectory_length 设多少合适

控制 Worker 保留多少轮截图历史（影响上下文长度和 API 费用）：
- 默认值：8
- 短任务（5步内）：4 足够
- 复杂任务（10步以上）：8~12

---

## 12 关键代码速查

### 坐标解析入口（双模型）

```
gui_agents/s3/agents/grounding.py
  OSWorldACI.generate_coords()  行 ~229
```

### 坐标解析入口（单模型）

```
gui_agents/s3/agents/grounding.py
  DirectACI._px()  行 ~720
```

### Worker 系统提示词

```
gui_agents/s3/memory/procedural_memory.py
  PROCEDURAL_MEMORY.construct_simple_worker_procedural_memory()
```

### 主循环（截图 → 预测 → 执行）

```
gui_agents/s3/cli_app.py
  run_agent()  行 ~155
```

### LLM 调用（带重试）

```
gui_agents/s3/utils/common_utils.py
  call_llm_safe()      普通调用，3次重试
  call_llm_formatted() 调用 + 格式校验，最多3次
```

### 新增的 DirectACI 类

```
gui_agents/s3/agents/grounding.py
  class DirectACI(OSWorldACI)  行 ~710
```

---

## 附：本次 git 提交记录

| Commit | 说明 |
|--------|------|
| `0477359` | 修复 Grounding 坐标解析——支持归一化浮点（kimi） |
| `04f6d1e` | 新增 USAGE.md 使用文档 |
| `d9ced0a` | 修复 0-1000 整数坐标（qwen）+ 推理文字重试机制 |
| `6449841` | 新增 DirectACI 单模型直出模式（--direct 参数） |
| `c681b7e` | 修复 DirectACI 坐标归一化（_px() 方法） |
| `560190e` | 文档扩充，完整操作手册 |

---

## 13 S3 代码架构深度梳理

> 我们用的是 S3 版本。这一节从源码层面详细说明 S3 的每个模块是什么、为什么这么设计，以及各模块之间如何协作。

### 13.1 S3 的核心设计思想

S3 相比 S1/S2 最大的改变是**去掉层级结构**。

S1/S2 有 Master Agent → Specialist Agent 两层：Master 分解任务，Specialist 执行子任务，每步需要多次 LLM 调用。S3 直接用一个 Worker 处理所有事情，**推理速度更快，API 花费更少**，同时在基准测试上反而表现更好（72.60%，首次超越人类）。

```
S1/S2 架构（多层）:              S3 架构（扁平）:
  Master Agent                    Worker Agent
    ↓ 分解任务                      ↓ 直接决策
  Specialist Agent                 ACI (动作执行)
    ↓ 执行                          ↓
  ACI                            pyautogui
```

### 13.2 目录结构与文件职责

```
gui_agents/s3/
│
├── cli_app.py                  # CLI 入口，截图主循环
│
├── agents/
│   ├── agent_s.py              # AgentS3：顶层编排，只有 3 行真正的逻辑
│   ├── worker.py               # Worker：核心推理，决定下一步做什么
│   ├── grounding.py            # ACI/OSWorldACI/DirectACI：把决策翻译成鼠标键盘代码
│   └── code_agent.py           # CodeAgent：执行 Python/Bash 代码的子 agent
│
├── core/
│   ├── module.py               # BaseModule：所有 agent 组件的基类
│   ├── mllm.py                 # LMMAgent：统一 LLM 调用封装
│   └── engine.py               # 各 provider 的底层 API 客户端
│
├── memory/
│   └── procedural_memory.py    # 所有系统提示词（静态常量 + 动态生成）
│
├── utils/
│   ├── common_utils.py         # LLM 调用工具（重试、格式化、代码解析）
│   ├── formatters.py           # 格式校验器（验证模型输出格式合法）
│   └── local_env.py            # 本地代码执行沙箱
│
└── bbon/
    ├── behavior_narrator.py    # 给截图标注动作轨迹（用于 bBoN）
    └── comparative_judge.py    # 比较多条轨迹，选最优（用于 bBoN）
```

### 13.3 完整执行流程（代码级）

一个任务步骤的完整调用链：

```
cli_app.py: run_agent()
│
│  1. 截图
│     screenshot = pyautogui.screenshot()
│     obs["screenshot"] = screenshot_bytes
│
│  2. 调用 agent
│     info, code = agent.predict(instruction, obs)
│
├─> agent_s.py: AgentS3.predict()
│       executor_info, actions = self.executor.generate_next_action(instruction, obs)
│       # executor 就是 Worker 实例
│
├─> worker.py: Worker.generate_next_action()
│   │
│   │  a. 把截图和任务绑定到 ACI
│   │     self.grounding_agent.assign_screenshot(obs)
│   │
│   │  b. 可选：调用反思模型
│   │     reflection = self._generate_reflection(instruction, obs)
│   │
│   │  c. 拼装 generator_message（反思文字 + 知识库 + 上一步code结果）
│   │
│   │  d. 调用主模型（带格式校验，最多重试3次）
│   │     plan = call_llm_formatted(self.generator_agent, format_checkers)
│   │     # 模型输出示例：
│   │     # (Screenshot Analysis) 当前屏幕显示微信界面...
│   │     # (Next Action) 点击搜索框输入联系人名称
│   │     # (Grounded Action)
│   │     # ```python
│   │     # agent.click(0.227, 0.106)
│   │     # ```
│   │
│   │  e. 解析代码块
│   │     plan_code = parse_code_from_string(plan)
│   │     # 提取到: "agent.click(0.227, 0.106)"
│   │
│   │  f. 执行代码，把抽象动作转成 pyautogui 代码
│   │     exec_code = create_pyautogui_code(grounding_agent, plan_code, obs)
│   │     # eval("agent.click(0.227, 0.106)") 触发 DirectACI.click(0.227, 0.106)
│   │     # 返回: "import pyautogui; pyautogui.click(435, 114, clicks=1, button='left');"
│   │
│   └─> 返回 (executor_info, [exec_code])
│
│  3. 执行动作
│     exec(code[0])
│     # 真正移动鼠标、点击
│
└─> 下一步循环
```

### 13.4 agent_s.py — 顶层编排（最简单）

```python
class AgentS3(UIAgent):
    def reset(self):
        self.executor = Worker(...)   # 创建 Worker

    def predict(self, instruction, observation):
        executor_info, actions = self.executor.generate_next_action(
            instruction=instruction, obs=observation
        )
        return info, actions
```

AgentS3 本身**只有 3 行逻辑**，它只是把 Worker 包装了一下，提供统一的 `predict()` 接口。真正的智能全在 Worker 里。

S1/S2 的 `predict()` 里还有 Master Agent 分解任务的逻辑，S3 直接去掉了。

### 13.5 worker.py — 核心推理（最重要）

Worker 是整个系统智能的核心，负责：

**维护两个 LMMAgent 实例**：

| Agent | 用途 | 系统提示词 |
|-------|------|-----------|
| `generator_agent` | 生成下一步动作 | 由 `procedural_memory` 动态构建，包含所有可用方法签名 |
| `reflection_agent` | 分析轨迹是否在循环卡住 | `REFLECTION_ON_TRAJECTORY` 常量 |

**消息历史管理（flush_messages）**：

```python
def flush_messages(self):
    if engine_type in ["anthropic", "openai", "gemini"]:
        # 长上下文模型：保留全部文字，只保留最新 k 张截图
        # （截图是大头，文字很小）
        max_images = self.max_trajectory_length
        for i in range(len(agent.messages) - 1, -1, -1):
            if img_count > max_images:
                del agent.messages[i]["content"][j]  # 删旧图
    else:
        # 短上下文模型（vLLM 等）：直接删整轮对话
        if len(messages) > 2 * max_trajectory_length + 1:
            messages.pop(1)
            messages.pop(1)
```

这个设计很重要：**保留文字历史但丢弃旧截图**。截图占 Token 大头，文字（plan、reflection）则很小，这样可以让模型记住"做过什么"同时控制成本。

**格式校验机制**：

Worker 用 `call_llm_formatted()` 调用模型，同时传入两个格式校验器：

```python
format_checkers = [
    SINGLE_ACTION_FORMATTER,    # 检查：只能有一个 agent.xxx() 调用
    CODE_VALID_FORMATTER,       # 检查：agent.xxx() 能成功转成 pyautogui 代码
]
plan = call_llm_formatted(self.generator_agent, format_checkers)
```

如果格式不对，会把错误信息发回给模型，让它重新输出，最多重试 3 次。

### 13.6 grounding.py — 动作层（设计最精妙）

这个文件定义了"模型能做什么动作"，是系统的**接口定义层**。

**@agent_action 装饰器**：

```python
def agent_action(func):
    func.is_agent_action = True   # 打上标记
    return func
```

只要给方法加这个装饰器，两件事自动发生：
1. `procedural_memory.py` 会自动把这个方法的签名和 docstring 注入系统提示词
2. 模型学会了调用它，`eval("agent.click(...)")` 就能执行

**OSWorldACI（双模型模式）的 click 完整流程**：

```python
@agent_action
def click(self, element_description: str, num_clicks=1, button_type="left", hold_keys=[]):
    # 1. 调用 Grounding 模型，把描述转成坐标
    coords = self.generate_coords(element_description, self.obs)
    # 2. 坐标缩放（从 grounding 分辨率转到屏幕分辨率）
    x, y = self.resize_coordinates(coords)
    # 3. 拼装 pyautogui 代码字符串（注意：是返回字符串，不是直接执行！）
    return f"import pyautogui; pyautogui.click({x}, {y}, clicks={num_clicks}, button={repr(button_type)})"
```

**注意关键点**：`click()` 方法**不执行**鼠标操作，它只返回一个 Python 代码字符串。真正的执行在 `cli_app.py` 里的 `exec(code[0])`。

**DirectACI（单模型模式）的 click**：

```python
@agent_action
def click(self, x: int, y: int, num_clicks=1, button_type="left", hold_keys=[]):
    # _px() 自动处理三种坐标格式
    px, py = self._px(x, y)
    return f"import pyautogui; pyautogui.click({px}, {py}, ...)"
```

没有 Grounding 模型调用，省了一次 API。

**所有可用动作一览**：

| 动作 | OSWorldACI 参数 | DirectACI 参数 | 说明 |
|------|----------------|----------------|------|
| `click` | `element_description` | `x, y` | 鼠标点击 |
| `type` | `element_description, text` | `x, y, text` | 输入文字（中文用剪贴板） |
| `scroll` | `element_description, clicks` | `x, y, clicks` | 滚动 |
| `drag_and_drop` | `start_desc, end_desc` | `start_x/y, end_x/y` | 拖拽 |
| `highlight_text_span` | `start_phrase, end_phrase` | `x1/y1, x2/y2` | 文字选取 |
| `hotkey` | `keys` | `keys` | 快捷键 |
| `hold_and_press` | `hold_keys, press_keys` | 同左 | 组合按键 |
| `open` | `app_or_filename` | 同左 | 打开应用/文件 |
| `switch_applications` | `app_code` | 同左 | 切换应用 |
| `save_to_knowledge` | `text` | 同左 | 存入知识库 |
| `call_code_agent` | `task` | 同左 | 调用代码执行子 agent |
| `wait` | `time` | 同左 | 等待 |
| `done` | — | — | 任务完成 |
| `fail` | — | — | 任务失败 |

### 13.7 core/mllm.py — 统一 LLM 封装

`LMMAgent` 是所有 LLM 调用的统一入口，屏蔽了不同 provider 的差异：

```python
class LMMAgent:
    def __init__(self, engine_params, system_prompt=None):
        # 根据 engine_type 自动选择 provider
        engine_type = engine_params["engine_type"]
        if engine_type == "openai":
            self.engine = LMMEngineOpenAI(**engine_params)
        elif engine_type == "anthropic":
            self.engine = LMMEngineAnthropic(**engine_params)
        # ... 8 种 provider

        self.messages = []  # 对话历史
        self.add_system_prompt(system_prompt)

    def add_message(self, text_content, image_content=None, role="user"):
        # 把截图（bytes）自动 Base64 编码后拼进消息
        # 支持同一消息里放多张图

    def get_response(self, temperature=0.0):
        # 调用 engine.generate(self.messages)
```

**消息格式**（OpenAI 风格，所有 provider 统一）：

```python
self.messages = [
    {
        "role": "system",
        "content": [{"type": "text", "text": "你是一个GUI操作专家...（含所有方法签名）"}]
    },
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "The initial screen is provided..."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ]
    },
    {
        "role": "assistant",
        "content": [{"type": "text", "text": "(Screenshot Analysis)...\nagent.click(0.227, 0.106)"}]
    },
    # ... 每步追加一个 user（截图）+ assistant（动作）对
]
```

### 13.8 core/engine.py — Provider 适配层

每个 provider 实现 `generate(messages, temperature)` 方法：

```python
class LMMEngineOpenAI(LMMEngine):
    @backoff.on_exception(backoff.expo, (APIConnectionError, RateLimitError), max_time=60)
    def generate(self, messages, temperature=0.0):
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            ).choices[0].message.content
        )
```

`@backoff.on_exception` 装饰器实现**指数退避重试**：遇到连接错误或限流自动等待重试，最长等 60 秒。

我们用的是 `LMMEngineOpenAI`（兼容接口），kimi-k2.5 和 qwen3.5-plus 都通过 `base_url` 指向阿里云百炼，用 OpenAI 格式调用。

### 13.9 memory/procedural_memory.py — 系统提示词工厂

这是理解整个系统的关键文件之一。Worker 的系统提示词**不是手写的**，而是由这个模块动态生成。

**动态注入过程**：

```python
@staticmethod
def construct_simple_worker_procedural_memory(agent_class, skipped_actions):
    procedural_memory = """
    你是 GUI 操作专家，负责执行任务 TASK_DESCRIPTION...
    你可以使用以下方法：
    class Agent:
    """

    # 反射：扫描 ACI 类的所有 @agent_action 方法
    for attr_name in dir(agent_class):
        attr = getattr(agent_class, attr_name)
        if callable(attr) and hasattr(attr, "is_agent_action"):
            signature = inspect.signature(attr)
            procedural_memory += f"""
    def {attr_name}{signature}:
    '''{attr.__doc__}'''
            """

    procedural_memory += """
    你的回复格式：
    (Screenshot Analysis) 当前屏幕描述...
    (Next Action) 下一步用自然语言描述...
    (Grounded Action)
    ```python
    agent.click(...)  # 只能一个动作
    ```
    """
    return procedural_memory
```

**效果对比**：

```
传给 OSWorldACI 时，模型看到:          传给 DirectACI 时，模型看到:
def click(                              def click(
    element_description: str,              x: int,
    num_clicks: int = 1,                   y: int,
    button_type: str = "left",             num_clicks: int = 1,
    hold_keys: List = [],                  button_type: str = "left",
):                                         hold_keys: List = [],
'''Click on the element                ):
Args:                                  '''Click at the specified pixel coordinate
    element_description: a detailed    Args:
    description...'''                      x: x pixel coordinate to click
                                           y: y pixel coordinate to click'''
```

模型根据 docstring 的参数描述决定输出格式，所以我们改了签名就等于改了模型的行为，**不需要手动写提示词**。

### 13.10 utils/common_utils.py — 执行粘合层

几个关键函数：

**`create_pyautogui_code(agent, code, obs)`**：

```python
def create_pyautogui_code(agent, code, obs):
    agent.assign_screenshot(obs)  # 先把截图给 ACI
    exec_code = eval(code)        # eval("agent.click(0.472, 0.978)") 触发 ACI.click()
    return exec_code              # 返回 pyautogui 代码字符串
```

这是"把模型输出的 Python 表达式执行一遍"的地方。`eval()` 调用 ACI 的方法（可能触发 Grounding API），得到 pyautogui 字符串，之后再在 `cli_app.py` 里 `exec()` 真正执行。

**`call_llm_formatted(generator, format_checkers)`**：

```python
def call_llm_formatted(generator, format_checkers):
    for attempt in range(3):
        response = call_llm_safe(generator)

        # 检查格式
        feedback_msgs = []
        for checker in format_checkers:
            success, feedback = checker(response)
            if not success:
                feedback_msgs.append(feedback)

        if not feedback_msgs:
            break  # 格式正确，退出

        # 格式错误：把错误信息追加到对话，让模型重新回答
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"格式错误：{feedback_msgs}"})
```

这是"自修复"机制：模型输出格式不对时，把错误告诉模型，模型自己改。

### 13.11 utils/formatters.py — 格式校验器

两个关键校验器，在 Worker 里用：

```python
# 校验 1：代码块里只能有一个 agent.xxx() 调用
SINGLE_ACTION_FORMATTER = lambda response: (
    len(extract_agent_functions(parse_code_from_string(response))) == 1,
    "必须只有一个 agent action"
)

# 校验 2：这个 agent.xxx() 调用是合法的（能成功转成 pyautogui 代码）
CODE_VALID_FORMATTER = lambda agent, obs, response: (
    _attempt_code_creation(agent, parse_code_from_string(response), obs) is not None,
    "agent action 必须是有效的方法调用"
)
```

校验 2 的副作用：它会尝试调用 ACI 方法（对于 OSWorldACI 会触发 Grounding API），所以格式校验本身也做了 Grounding。

### 13.12 code_agent.py — 代码执行子 Agent

当 Worker 决定调用 `agent.call_code_agent()` 时，会启动 CodeAgent 执行复杂的代码任务（最多 20 步）：

```
Worker 调用 agent.call_code_agent("计算B列总和")
    ↓
CodeAgent.execute(task, screenshot, env_controller)
    ↓ 循环（最多 20 步）
    ├── 1. 调用 LLM：分析任务，输出 Python/Bash 代码
    │   模型输出：
    │   <thoughts> 需要找到B列数据范围... </thoughts>
    │   <answer>
    │   ```python
    │   import openpyxl
    │   wb = openpyxl.load_workbook('data.xlsx')
    │   ...
    │   ```
    │   </answer>
    │
    ├── 2. 提取代码块
    ├── 3. 执行：LocalController.run_python_script(code)
    ├── 4. 把执行结果（stdout/stderr）发回给 LLM
    └── 5. 检测 DONE/FAIL 或继续

返回执行摘要给 Worker
```

CodeAgent 适合：电子表格操作、文件批处理、数据分析等纯代码能完成的任务。不适合：需要看界面、点击按钮的 GUI 任务。

### 13.13 bbon/ — 最优轨迹选择（高级功能）

bBoN（Behavior Best-of-N）是 S3 的高级功能：运行 N 条轨迹，选最好的那条。

```
运行轨迹 1 → 截图序列 1
运行轨迹 2 → 截图序列 2
运行轨迹 3 → 截图序列 3
     ↓
BehaviorNarrator: 给每个动作的前后截图配上文字说明
     ↓
ComparativeJudge: 用 VLM 比较三条轨迹的初始/最终截图，选最优
```

日常使用不需要 bBoN，它主要用于提高基准测试成绩。

### 13.14 我们做的改动总结

在原始 S3 之上，我们添加了：

| 改动 | 文件 | 作用 |
|------|------|------|
| `DirectACI` 类 | `grounding.py` | 单模型模式，跳过 Grounding API |
| `DirectACI._px()` | `grounding.py` | 自动识别三种坐标格式并转换 |
| `--direct` CLI 参数 | `cli_app.py` | 启动时选择单/双模型模式 |
| 修复 `generate_coords()` | `grounding.py` | 支持 kimi 浮点坐标、qwen 0-1000坐标 |
| 添加重试机制 | `grounding.py` | kimi 输出推理文字时重问 |
