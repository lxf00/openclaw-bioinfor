# BioOpenClaw 远程部署执行手册

本手册用于将 BioOpenClaw 全项目部署到远程 Linux 服务器。

## 1. 先定义四个路径变量

以下变量全部使用远程服务器绝对路径，不要使用本地路径：

- `REPO_ROOT`：代码仓库根目录，例如 `/opt/bioopenclaw`
- `VENV_PY`：虚拟环境 Python，例如 `/opt/bioopenclaw/.venv/bin/python`
- `DATA_ROOT`：数据与共享目录根，例如 `/data/bioopenclaw`
- `OPENCLAW_HOME`：OpenClaw 根目录，例如 `/home/ubuntu/.openclaw`

先在 shell 里执行：

```bash
export REPO_ROOT=/opt/bioopenclaw
export VENV_PY=/opt/bioopenclaw/.venv/bin/python
export DATA_ROOT=/data/bioopenclaw
export OPENCLAW_HOME=/home/ubuntu/.openclaw
```

## 2. 拉代码并创建 Python 环境

```bash
mkdir -p "$REPO_ROOT"
cd "$REPO_ROOT"
# 首次部署：
# git clone <YOUR_REPO_URL> .
# 后续更新：
# git pull

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -e .
pip install -e ".[huggingface,dev]"
```

检查：

```bash
python --version
pip show mcp
python -c "import bioopenclaw; print('bioopenclaw import ok')"
```

## 3. 创建服务器目录结构

推荐直接用脚本准备运行布局：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/prepare_runtime_layout.py --repo-root "$REPO_ROOT" --data-root "$DATA_ROOT" --state-mode symlink
```

这会完成两件事：

- 创建 `DATA_ROOT/data`、`DATA_ROOT/models`、`DATA_ROOT/shared_memory`、`DATA_ROOT/agents` 及其子目录
- 让 `REPO_ROOT/agents` 和 `REPO_ROOT/shared_memory` 指向 `DATA_ROOT` 中的真实运行目录

这种“单一状态视图”是 Harness 正常工作的前提，因为当前 `bioopenclaw-harness` 默认从 `project_root/agents` 和 `project_root/shared_memory/inbox` 读取/写入状态。

如果你必须手工执行，等价关系应为：

```bash
ln -sfn "$DATA_ROOT/agents" "$REPO_ROOT/agents"
ln -sfn "$DATA_ROOT/shared_memory" "$REPO_ROOT/shared_memory"
```

## 4. 生成 `.env`

推荐使用配置生成脚本：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/generate_remote_configs.py \
  --repo-root "$REPO_ROOT" \
  --venv-py "$VENV_PY" \
  --data-root "$DATA_ROOT" \
  --openclaw-home "$OPENCLAW_HOME"
nano .env
```

至少填写：

- `DATA_AGENT_ENTREZ_EMAIL`
- `RESEARCH_AGENT_ENTREZ_EMAIL`
- `SCOUT_AGENT_HF_TOKEN`
- `MODEL_AGENT_HF_TOKEN`
- 可选：`DATA_AGENT_NCBI_API_KEY`
- 可选：`RESEARCH_AGENT_NCBI_API_KEY`

检查：

```bash
grep -E '^(DATA_AGENT_|SCOUT_AGENT_|RESEARCH_AGENT_|MODEL_AGENT_|WATCHER_|ENTREZ_EMAIL|HF_TOKEN)' .env
```

## 5. 生成服务器版 MCP 配置与 Harness Tool Map

`scripts/generate_remote_configs.py` 同时会生成：

- `REPO_ROOT/.env`
- `REPO_ROOT/mcp_config.remote.json`
- `REPO_ROOT/deploy/harness_tool_map.remote.generated.json`

默认会去掉 legacy `bioinformatics-tools`，只保留独立 agent MCP server。

检查：

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path("mcp_config.remote.json")
obj = json.loads(p.read_text(encoding="utf-8"))
for name, cfg in obj["mcpServers"].items():
    print(name)
    print("  command =", cfg["command"])
    print("  cwd     =", cfg["cwd"])
PY
```

同时确认 Harness tool map 已生成：

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path("deploy/harness_tool_map.remote.generated.json")
obj = json.loads(p.read_text(encoding="utf-8"))
print(json.dumps(obj, indent=2, ensure_ascii=False))
PY
```

## 6. 同步 6 个 OpenClaw prompt

先 dry-run：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/sync_openclaw_prompts.py --openclaw-home "$OPENCLAW_HOME" --dry-run
```

确认无误后执行：

```bash
python scripts/sync_openclaw_prompts.py --openclaw-home "$OPENCLAW_HOME"
```

检查：

```bash
ls "$OPENCLAW_HOME/agents/main/agent/system_prompt.md"
ls "$OPENCLAW_HOME/agents/data/agent/system_prompt.md"
ls "$OPENCLAW_HOME/agents/scout/agent/system_prompt.md"
ls "$OPENCLAW_HOME/agents/model/agent/system_prompt.md"
ls "$OPENCLAW_HOME/agents/research/agent/system_prompt.md"
ls "$OPENCLAW_HOME/agents/watcher/agent/system_prompt.md"
```

## 7. 在各 OpenClaw 实例绑定 MCP

建议最小绑定方式：

- `main`：按调度需要绑定 `data-agent`、`scout-agent`、`model-agent`、`research-agent`、`watcher`
- `data`：绑定 `data-agent`
- `scout`：绑定 `scout-agent`
- `model`：绑定 `model-agent`
- `research`：绑定 `research-agent`
- `watcher`：绑定 `watcher`

如果 OpenClaw 支持读取 MCP 配置文件：

```bash
cp "$REPO_ROOT/mcp_config.remote.json" "$OPENCLAW_HOME/mcp_config.remote.json"
```

然后在各实例配置里引用该文件，或者复制各自对应的 `mcpServers` 配置段。

## 8. 单服务冒烟测试

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/run_agent_smoke_tests.py
python scripts/test_mcp_connection.py
```

如果只想检查单模块能否启动导入：

```bash
python -m bioopenclaw.mcp_servers.scout_agent.server
python -m bioopenclaw.mcp_servers.model_agent.server
python -m bioopenclaw.mcp_servers.research_agent.server
python -m bioopenclaw.watcher.server
```

注意：这些是 stdio MCP 进程，只用于看能否启动，不要把它们当成 TCP 常驻服务。

## 9. 跨 Agent 最小闭环验收

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/run_cross_agent_e2e_check.py
python scripts/memory_consistency_check.py
python scripts/daily_log_archive.py --dry-run
```

如果要单独验证 inbox 分发：

```bash
python scripts/inbox_dispatch.py --dry-run --inbox-dir "$DATA_ROOT/shared_memory/inbox" --agents-dir "$DATA_ROOT/agents"
```

## 10. Harness 层回归测试

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python -m pytest tests/test_harness -q
```

## 11. Watcher 映射修复后的回归测试

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python -m pytest tests/test_integration/test_watcher_trigger_mapping.py -q
python -m pytest tests/test_integration -q
```

## 12. Harness CLI 冒烟验收

先用 `direct` 模式跑一个轻量任务：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/run_harness_smoke.py \
  --project-root "$REPO_ROOT" \
  --transport direct \
  --tool-map "$REPO_ROOT/deploy/harness_tool_map.remote.generated.json" \
  --title "Remote harness smoke" \
  --goal "Search literature and generate a first-pass hypothesis" \
  --success-criterion "report available" \
  --max-ticks 5
```

确认这些文件确实变化：

```bash
ls "$REPO_ROOT/.harness_state/runs"
ls "$REPO_ROOT/shared_memory/inbox"
ls "$REPO_ROOT/agents/watcher/corrections_log"
sed -n '1,120p' "$REPO_ROOT/agents/research_agent/active_context.md"
```

然后再切换到协议级 `stdio`：

```bash
python scripts/run_harness_smoke.py \
  --project-root "$REPO_ROOT" \
  --transport stdio \
  --tool-map "$REPO_ROOT/deploy/harness_tool_map.remote.generated.json" \
  --title "Remote harness protocol smoke" \
  --goal "Search literature and generate a first-pass hypothesis" \
  --success-criterion "stdio mcp call succeeds" \
  --max-ticks 5
```

## 13. OpenClaw -> multi-agent -> watcher 人工联调

在 OpenClaw 实例里按这个顺序操作：

1. 在 `main` 中发送任务，例如：
   - “请为 BRCA1 乳腺癌单细胞研究准备数据，并给出后续模型建议”
2. 观察是否路由到 `data`
3. `data` 完成后检查 inbox：

```bash
ls "$DATA_ROOT/shared_memory/inbox"
```

4. 运行消息分发：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/inbox_dispatch.py --inbox-dir "$DATA_ROOT/shared_memory/inbox" --agents-dir "$DATA_ROOT/agents"
```

5. 检查目标 agent 是否收到消息：

```bash
sed -n '1,120p' "$DATA_ROOT/agents/model_agent/active_context.md"
```

6. 检查 watcher 纠偏日志：

```bash
ls "$DATA_ROOT/agents/watcher/corrections_log"
```

## 14. 日常巡检命令

每日：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/memory_consistency_check.py
python scripts/inbox_dispatch.py --dry-run --inbox-dir "$DATA_ROOT/shared_memory/inbox" --agents-dir "$DATA_ROOT/agents"
```

每周：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/memory_rotate.py
python scripts/daily_log_archive.py
```

Scout 定期扫描：

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python scripts/scout_scan.py --days 7 --limit 20 --dry-run
python scripts/scout_scan.py --days 7 --limit 20
```

## 15. 回滚命令

```bash
cd "$REPO_ROOT"
git log --oneline -n 10
# 选一个稳定提交
# git checkout <stable_commit_or_tag>

source .venv/bin/activate
python scripts/run_agent_smoke_tests.py
python scripts/memory_consistency_check.py
```

如果保留了服务器专用备份配置：

```bash
cp "$REPO_ROOT/mcp_config.remote.json.bak" "$REPO_ROOT/mcp_config.remote.json"
cp "$REPO_ROOT/.env.bak" "$REPO_ROOT/.env"
```

## 16. 最终上线前一次性执行

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/run_agent_smoke_tests.py && \
python scripts/test_mcp_connection.py && \
python scripts/run_cross_agent_e2e_check.py && \
python scripts/memory_consistency_check.py && \
python -m pytest tests/test_integration -q && \
python -m pytest tests/test_harness -q
```

全部通过后，再去 OpenClaw 6 个实例做最终人工联调。

## 17. 最快执行顺序

你现在最应该先执行这 5 组命令：

```bash
export REPO_ROOT=/opt/bioopenclaw
export VENV_PY=/opt/bioopenclaw/.venv/bin/python
export DATA_ROOT=/data/bioopenclaw
export OPENCLAW_HOME=/home/ubuntu/.openclaw
cd "$REPO_ROOT" && source .venv/bin/activate
```

```bash
python scripts/prepare_runtime_layout.py --repo-root "$REPO_ROOT" --data-root "$DATA_ROOT" --state-mode symlink
python scripts/generate_remote_configs.py \
  --repo-root "$REPO_ROOT" \
  --venv-py "$VENV_PY" \
  --data-root "$DATA_ROOT" \
  --openclaw-home "$OPENCLAW_HOME"
nano .env
```

```bash
python scripts/sync_openclaw_prompts.py --openclaw-home "$OPENCLAW_HOME"
```

```bash
python scripts/run_agent_smoke_tests.py && \
python scripts/run_cross_agent_e2e_check.py && \
python scripts/memory_consistency_check.py && \
python -m pytest tests/test_harness -q
```

```bash
python scripts/run_harness_smoke.py \
  --project-root "$REPO_ROOT" \
  --transport direct \
  --tool-map "$REPO_ROOT/deploy/harness_tool_map.remote.generated.json" \
  --title "Remote harness smoke" \
  --goal "Search literature and generate a first-pass hypothesis" \
  --success-criterion "report available" \
  --auto-run \
  --max-ticks 5
```

