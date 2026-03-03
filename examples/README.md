# Examples

All examples use DirectACI (single-model mode). Set your API key before running:

```bash
export OPENAI_API_KEY=sk-...
# For DashScope (China):
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## Examples

| File | Description |
|------|-------------|
| `wechat_demo.py` | Send a message in WeChat via GUI automation |

## Running

```bash
# Default task (WeChat message to Zhang San)
python examples/wechat_demo.py

# Custom task
python examples/wechat_demo.py "Open Chrome and go to github.com"

# Different model
AUTOACT_MODEL=qwen-vl-max python examples/wechat_demo.py "Open Notepad"
```
