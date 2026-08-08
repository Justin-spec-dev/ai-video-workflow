# AI Video Workflow

节点式 AI 视频生产工作台（类似 ComfyUI / n8n，但完全独立实现）。在无限画布中通过拖拽和连接节点，自由组合 Prompt、Prompt Optimizer（LLM）、Context、MiniMax H3 视频生成、尾帧提取、视频拼接等能力。**全中文界面**。

- **可扩展 Provider 架构**：新增 Kling / Veo / Seedance / Runway 等视频 Provider 或 OpenAI / Anthropic 等 LLM Provider 时，只需实现 Provider 接口并注册，**Workflow Engine 零改动**。
- **统一 Node 接口**：新增节点 = 实现 `BaseNode` + 注册到 `NodeRegistry`，Engine 不包含任何业务逻辑。
- **快速开始**：内置 5 个场景模板（文生视频/图生视频/连续镜头/三镜头短片/故事分镜），选场景 → 填提示词（多镜头场景逐镜头填写）→ 选分辨率/时长 → 一键创建可运行的工作流。
- **安全**：API Key 只保存在后端（Fernet 加密），Workflow JSON / 前端 LocalStorage / 日志中绝不出现明文。
- **数据安全网**：每次保存自动备份（`backend/data/backups/`），删除的工作流先进回收站（`backend/data/trash/`），误删可恢复；空提示词在调用付费 API 前本地拦截，不产生费用。

## Requirements

- Python 3.11+
- Node.js 18+ 与 npm
- FFmpeg / FFprobe（视频处理节点必需）

## Quick Start

```bash
git clone https://github.com/Justin-spec-dev/ai-video-workflow.git
cd ai-video-workflow
```

### Windows

双击 `start.bat`。它会自动：检查环境 → 创建 venv 装依赖 → 启动 FastAPI(8000) → 启动 Frontend(5173) → 打开浏览器。

### Linux / macOS / WSL

```bash
./start.sh
```

或手动：

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8000

# Frontend（另一个终端）
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 。

### Docker

```bash
docker compose up --build
```

## 界面快速上手

1. 顶栏「**凭证**」→ 配置 LLM（OpenAI 兼容，如 DeepSeek）和视频（MiniMax）两套凭证，点「测试连接」确认。
2. 顶栏「**✨ 快速开始**」→ 选场景卡片 → 填提示词（连续镜头/三镜头需逐段填写，全部必填）→ 选分辨率/时长/比例 → 「创建工作流」。
3. 画布上确认节点连接无误 → 顶栏「**运行**」→ 付费确认弹窗显示预估（付费节点数/调用次数/视频时长）→ 确认后开始生成。
4. 生成完成后视频直接在节点上内嵌播放；底部面板可查看日志/任务/运行历史/成本。
5. 画布自动保存（1.5s 防抖），刷新自动恢复上次工作流与最近一次运行结果；顶栏可直接改名，「文件 → 打开工作流」里可切换/删除（删除进回收站）。

## FFmpeg Setup

查找顺序：环境变量 `FFMPEG_PATH` → 项目内 `tools/ffmpeg/ffmpeg` → 系统 PATH。
Windows 用户请下载 FFmpeg 并把 `ffmpeg.exe` / `ffprobe.exe` 放入 `tools/ffmpeg/` 或加入 PATH。

## MiniMax Configuration（H3）

1. 在 [MiniMax 开放平台](https://platform.minimax.io) 获取 API Key（国内站为 `platform.minimaxi.com`）。
2. 打开 Web UI → 顶栏「**凭证**」→ 视频组 →「添加」：
   - Provider: `MiniMax`
   - Name: 如 `MiniMax-Personal`
   - Base URL: 海外默认 `https://api.minimax.io`，国内填 `https://api.minimaxi.com`
   - API Key: 你的 Key（只存后端，加密保存）
3. 点击 **Test Connection**，显示 `✓ Connected` 即可。

## LLM Configuration（Prompt Optimizer / LLM / Storyboard）

任何 OpenAI 兼容端点（DeepSeek、Qwen、GPT、本地 vLLM/Ollama 等）：

1. 顶栏「**凭证**」→ LLM 组 →「添加」：Provider `OpenAI Compatible`，填 Base URL（如 `https://api.deepseek.com/v1`）与 API Key（模型如 `deepseek-v4-flash`）。
2. 在提示词优化器节点属性中独立选择该凭证与模型 —— 与视频生成的 MiniMax 凭证**完全独立**。

## Workflow Tutorial

- 左侧面板拖入节点（或双击画布 / 按 `Space` 搜索添加）。
- 端口有类型（TEXT/PROMPT/IMAGE/VIDEO/JSON…），非法连接会被即时拒绝（如 `VIDEO → PROMPT`）。
- 快捷键：`Delete` 删除、`Ctrl+C/V` 复制粘贴、`Ctrl+Z / Ctrl+Shift+Z` 撤销重做、`Ctrl+S` 保存。
- 画布修改 1.5s 后自动保存，刷新页面自动恢复。
- 右键节点：Run Node / Run From Here / Retry / Clear Cache / Inspect Input/Output。
- 顶部 **File → New From Template** 可加载内置模板（Text to Video / Image to Video / Last Frame Continue / Three Shot Movie / Story to Storyboard）。

## Prompt Optimizer Tutorial

`Prompt → Prompt Optimizer → Video Generation`。

- 模式：`Optimize`（保留原意提质）/ `Expand`（短句扩写）/ `Structured`（Scene/Subject/Action/Camera/Lighting… 结构化）/ `Rewrite`（按你的要求重写，如"镜头运动更明显"）。
- **Target Video Model** 可选 `Generic` / `MiniMax H3`（预留 Kling/Veo/Seedance），不同目标模型使用不同的优化策略。
- 运行后在右侧属性面板查看 **Original vs Optimized** 对比，可 Edit / Regenerate / Restore Original / Accept —— 确认后才接视频生成，避免直接付费。
- 可接入 `Character / Scene / Style Context` 节点，保持多镜头人物与风格一致。

## H3 Tutorial（MiniMax 视频生成）

- 模型：`MiniMax-H3`；分辨率 `768P` / `2K`；时长 4–15 秒整数；比例 `16:9` 等（纯文本时必选，图生视频自动 adaptive）。
- 输入：`prompt`（必填）、`image`（首帧，可选）、`last_frame_image`（尾帧，须与首帧同用）。
- 本地图片自动转为 data URI 上传（图片 ≤30MB、请求体 ≤64MB）。
- 执行流程：创建任务 → 保存 remote `task_id` → 轮询（默认 10s）→ 下载到 `outputs/`。后端重启后可凭 `task_id` 恢复。
- 付费保护：Run 前弹出成本确认；`Settings` 可配置 `require_confirmation` / `max_paid_tasks_per_run` / `max_estimated_cost_per_run` / `pricing.minimax.per_second`（不填单价则显示 "Cost unavailable"，绝不虚构费用）。

## Last Frame Tutorial

`Video → Last Frame → 下一个 Video 的 image 输入`，实现连续镜头（Shot Chain）：

```text
Prompt#1 → Optimizer#1 → Video#1 → Last Frame ──┐
Prompt#2 → Optimizer#2 ───────────────────────→ Video#2 → Last Frame → Video#3 …
```

`Frame Extract` 节点还支持 First Frame / Timestamp（如 3.5s）/ Percentage（如 50%）。

## Video Merge Tutorial

多个视频输出连入 `Video Merge` 的 `videos`（VIDEO[]）输入 → 输出合并后的 `final.mp4`。优先 stream copy（无损秒合），编码/分辨率不一致时自动回退 re-encode，优先保证合并成功。

## Output 文件结构

```text
backend/outputs/<workflow-name>/run_<ts>_<id>/
├── nodes/<node_id>/…        # 各节点产物（视频/图片/prompt.txt）
└── …
```

运行之间互不覆盖。`Save File` 节点可额外导出到指定目录。

## API 概览

全部 REST 以 `/api` 为前缀：`/nodes` `/templates` `/workflows` `/runs` `/tasks` `/credentials` `/providers` `/files` `/settings` `/shots`；实时事件走 `ws://…/ws/events`（`node.running` / `task.processing` / `log` / `workflow.finished` 等）。完整契约见 `docs/SPEC.md`。

## 新增 Provider / Node（扩展指南）

- 视频 Provider：继承 `backend/app/providers/video/base.py` 的 `VideoProvider`，实现 `create_task / get_task_status / download / cancel / test_connection`，注册即可被 `video_generation` 节点选用。
- 节点：继承 `backend/app/nodes/base.py` 的 `BaseNode`，声明 `inputs/outputs/config_schema`，实现 `execute()`，在 `nodes/__init__.py` 导入即完成注册。Engine 无需任何修改。

## Troubleshooting

| 问题 | 排查 |
|---|---|
| Test Connection 401 | API Key 错误或 Base URL 区域不对（海外 `.io` / 国内 `.com`） |
| 视频节点一直 queued/running | 正常，H3 生成需数分钟；在 Tasks 面板点 Refresh 查看远端状态 |
| 尾帧/合并失败 | 确认 FFmpeg 可用：后端日志启动时会打印 ffmpeg 路径 |
| 图生视频报错 ratio | 有首/尾帧时比例固定 adaptive，无需设置 |
| 单独使用尾帧报错 | 官方 API 要求 `last_frame` 必须与 `first_frame` 成对出现 |
| 付费运行被拒绝 409 | 超过 Settings 中的付费任务数/费用上限 |
| 端口被占用 | 改 `start.bat/sh` 中端口号与 `frontend/vite.config.ts` 代理目标 |

日志：`backend/data/server.log`；Web UI 底部 Logs 面板实时显示运行日志。

## 测试

```bash
cd backend && .venv/bin/python -m pytest tests/ -v   # 67 项测试
cd frontend && npm run build                          # 类型检查 + 构建
```
