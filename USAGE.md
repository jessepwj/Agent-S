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
