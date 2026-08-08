# AI Video Workflow — 架构契约（前后端共同遵守）

本文档是前后端实现的唯一权威契约。任何接口、数据结构、事件名都必须以本文档为准。

## 0. 总体

- Backend: Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async, aiosqlite) / Pydantic v2 / httpx / asyncio。端口 **8000**。所有 REST 路由挂载在 `/api` 前缀下，WebSocket 为 `/ws/events`。
- Frontend: React 18 + TypeScript + Vite + @xyflow/react + Zustand + Tailwind CSS。端口 **5173**，Vite dev proxy 把 `/api` 与 `/ws` 转发到 `http://localhost:8000`。
- 项目根：`/home/wsl/code/work/ai-video-workflow/`（下记 `$ROOT`）。
- FFmpeg 静态二进制已存在于 `$ROOT/../tools/ffmpeg/ffmpeg` 与 `$ROOT/../tools/ffmpeg/ffprobe`（即项目外的 `tools/`）。Backend 查找顺序：env `FFMPEG_PATH` → `$ROOT/tools/ffmpeg/ffmpeg`（项目内 tools 软链或拷贝）→ 系统 PATH。**实现时把仓库内 `ai-video-workflow/tools/ffmpeg/` 作为默认查找路径之一**（主会话已把二进制放在 `work/tools/ffmpeg/`，backend agent 应在 `ai-video-workflow/tools/` 下创建指向它们的拷贝或软链）。

## 1. 目录结构

```text
ai-video-workflow/
├── frontend/
│   ├── src/
│   │   ├── components/      # 布局、面板、通用 UI（含 components/ui/ shadcn 风格组件）
│   │   ├── nodes/           # 自定义节点 React 组件（动态 schema 渲染）
│   │   ├── workflow/        # 画布、边校验、快捷键、模板
│   │   ├── stores/          # zustand stores
│   │   ├── api/             # REST + WS client
│   │   ├── hooks/
│   │   └── types/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routers
│   │   ├── core/            # config, database, events, security(加密/脱敏)
│   │   ├── nodes/           # BaseNode, registry, 所有节点实现
│   │   ├── providers/       # llm/, video/ (minimax), base 接口
│   │   ├── credentials/     # CredentialService
│   │   ├── workflow/        # engine, dag, context, cache, runner
│   │   ├── services/        # ffmpeg, files, cost, templates
│   │   ├── models/          # SQLAlchemy ORM + Pydantic schemas
│   │   └── main.py
│   ├── tests/
│   ├── data/                # sqlite db, uploads, secret key（gitignore）
│   ├── outputs/
│   ├── temp/
│   └── requirements.txt
├── workflows/               # 导出的 workflow json 示例
├── docs/SPEC.md
├── tools/ffmpeg/            # ffmpeg/ffprobe 二进制（或指向它们的链接）
├── .env.example
├── README.md
├── start.bat
├── start.sh
└── docker-compose.yml
```

## 2. 端口类型系统（PortType）

字符串枚举：`TEXT, PROMPT, IMAGE, VIDEO, AUDIO, JSON, NUMBER, BOOLEAN, FILE`，以及数组形式 `TEXT[], PROMPT[], IMAGE[], VIDEO[], JSON[]`（数组形式用字符串 `"IMAGE[]"` 表示）。

连接兼容规则（前端连线即时校验 + 后端 DAG 校验二次检查）：
- 完全相同 → 允许。
- `PROMPT` → `TEXT` 允许；`TEXT` → `PROMPT` 允许（text 可作 prompt）。
- 其它组合一律禁止（尤其 `VIDEO → PROMPT`）。
- 数组类型只与同基类数组兼容（`PROMPT[]` 与 `TEXT[]` 按上面规则互通）。
- `VIDEO[]` 输入端口（如 Video Merge）接受多条 `VIDEO` 入边。

## 3. Node Schema（GET /api/nodes 返回的每个元素）

```jsonc
{
  "type": "prompt",                 // 唯一类型 id
  "name": "Prompt",
  "version": "1.0.0",
  "category": "Text",               // Input|Text|AI|Context|Image|Video|Logic|Utility|Output
  "description": "...",
  "is_paid": false,
  "inputs":  [{"key":"text","name":"Text","type":"TEXT","required":false,"multiple":false,"description":""}],
  "outputs": [{"key":"prompt","name":"Prompt","type":"PROMPT"}],
  "config_schema": [                 // 有序数组，驱动前端属性面板
    {"key":"text","name":"Text","type":"textarea","default":"","placeholder":"...","rows":6},
    {"key":"provider","name":"Provider","type":"select","options":["openai_compatible"],"default":"openai_compatible"},
    {"key":"credential_id","name":"Credential","type":"credential","provider_kind":"llm","default":null},
    {"key":"temperature","name":"Temperature","type":"number","default":0.7,"min":0,"max":2,"step":0.1},
    {"key":"enabled","name":"Enabled","type":"boolean","default":true}
  ]
}
```

`config_schema[].type` 允许值：`text, textarea, number, boolean, select, credential, model, json, file, slider`。
- `credential`：前端渲染为下拉，选项来自 `GET /api/credentials?kind=...`（只含 id/name，无 secret）。
- `model`：字符串输入（带 datalist 建议即可，不强制远端校验）。

节点输出值约定（execute 返回 dict 的 value）：
- TEXT/PROMPT: `str`；IMAGE/VIDEO/AUDIO/FILE: `{"path": "<相对 outputs 的绝对路径或项目内路径>", "url": "/api/files/...", "width":?, "height":?, "duration":?, "filename": ...}`；JSON: 任意 JSON；NUMBER/BOOLEAN: 原生值；数组：对应列表。
- 媒体对象必须含 `path`（后端绝对路径）与 `url`（前端可访问的 `/api/files/...`）。

## 4. Workflow JSON（保存格式，禁止含任何 secret）

```jsonc
{
  "version": 1,
  "name": "My Workflow",
  "nodes": [{"id":"n1","type":"prompt","position":{"x":0,"y":0},"config":{}}],
  "edges": [{"id":"e1","source":"n1","source_handle":"prompt","target":"n2","target_handle":"prompt"}],
  "viewport": {"x":0,"y":0,"zoom":1}
}
```
config 里只允许出现 `provider / model / credential_id` 等引用，**绝不出现 api_key**。

## 5. Backend 模块

### 5.1 BaseNode（backend/app/nodes/base.py）
```python
class BaseNode:
    type: str; name: str; version: str = "1.0.0"; category: str = "Utility"
    description: str = ""; is_paid: bool = False
    inputs: list[PortDef]; outputs: list[PortDef]; config_schema: list[ConfigField]
    async def execute(self, inputs: dict, config: dict, context: "ExecutionContext") -> dict: ...
    def schema(self) -> dict: ...   # 生成 §3 的 JSON
```
`NodeRegistry`：类装饰器 `@register_node` 或 `NODE_REGISTRY.register(cls)`；`get(type)`, `all_schemas()`。新增节点 = 新建文件实现 BaseNode + 在 `nodes/__init__.py` import，**Engine 零改动**。

### 5.2 节点清单（第一版必须全部实现）

| type | category | 说明 | inputs / outputs |
|---|---|---|---|
| `prompt` | Text | 多行 prompt，支持 `{{var}}` 模板渲染 | in: - ; out: prompt:PROMPT |
| `text` | Text | 纯文本 | out: text:TEXT |
| `combine_prompt` | Text | 模板 `{{character}}` 等 | in: character/scene/action/camera:PROMPT(optional); out: prompt:PROMPT |
| `variables` | Context | key=value 列表，输出注入 context.variables，也输出 TEXT | out: text:TEXT |
| `character_context` | Context | 姓名/年龄/性别/外貌/发型/服装/性格/必须保持特征 → 渲染文本 | out: prompt:PROMPT |
| `scene_context` | Context | 地点/时间/天气/环境/空间布局/持续物体 | out: prompt:PROMPT |
| `style_context` | Context | 画面风格/镜头语言/调色/光线/宽高比/胶片感 | out: prompt:PROMPT |
| `llm` | AI | OpenAI 兼容；in: system_prompt:TEXT, prompt:TEXT, context:TEXT(optional); out: text:TEXT, json:JSON(尝试解析，失败为 null) |
| `prompt_optimizer` | AI | 核心。in: prompt:PROMPT, character/scene/style:PROMPT(optional×3); out: prompt:PROMPT, original:PROMPT。config: mode(optimize/expand/structured/rewrite), rewrite_instruction, provider/credential_id/model/base_url/temperature/system_prompt(可留空用默认), target_video_model(generic/minimax_h3/kling/veo/seedance)。如果 config.edited_prompt 非空（用户在 Review 中改过），execute 直接输出 edited_prompt 而不再调用 LLM。 |
| `storyboard` | AI | in: story:TEXT; 用 LLM 生成 shots JSON（自带 system prompt）；out: json:JSON, prompts:PROMPT[], texts:TEXT[] |
| `json_parser` | Utility | in: json:JSON 或 text:TEXT; config: jsonpath（支持 `$..`、`$.shots[*].prompt` 子集：字段、索引、`[*]`）；out: json:JSON, text:TEXT, texts:TEXT[], prompts:PROMPT[] |
| `image_input` | Input | config: file（上传后存 path）；读取宽高；out: image:IMAGE（节点内嵌预览） |
| `video_generation` | Video | is_paid=true。in: prompt:PROMPT, image:IMAGE(optional), last_frame_image:IMAGE(optional); out: video:VIDEO。config: provider(minimax), credential_id, model, resolution, duration, ratio, retry_count, poll_interval, timeout |
| `last_frame` | Video | in: video:VIDEO; out: image:IMAGE（FFmpeg 提取最后一帧，存 run 目录） |
| `frame_extract` | Video | in: video:VIDEO; config: mode(first/last/timestamp/percentage), timestamp, percentage; out: image:IMAGE |
| `video_preview` | Video | in: video:VIDEO; out: video:VIDEO（透传） |
| `video_merge` | Video | in: videos:VIDEO[]（multiple=true）; config: reencode(auto/always); out: video:VIDEO。先 stream copy concat，失败回退 re-encode |
| `save_file` | Output | in: video:VIDEO/image:IMAGE/text:TEXT/json:JSON(均 optional，取第一个非空); config: directory, filename, overwrite(overwrite/rename/fail); out: file:FILE |

节点一律把产物写到 `context.node_output_dir`（engine 提供，形如 `outputs/<wf-slug>/run_<ts>/nodes/<node_id>/`），返回的媒体 dict 里 `url` 由后端统一规则生成（见 §9 文件服务）。

### 5.3 Provider 接口

```python
# providers/video/base.py
class VideoTaskRequest(BaseModel):  # prompt, first_frame_path|None, last_frame_path|None, duration, resolution, ratio, extra: dict
class VideoTaskStatus(BaseModel):   # task_id, status: queued|running|succeeded|failed|cancelled, video_url|None, error|None, raw: dict
class VideoProvider:
    name: str; display_name: str
    def config_schema(self) -> list[ConfigField]: ...        # provider 特有参数，并入节点 config_schema
    async def create_task(self, request, credential) -> str        # 返回 remote task_id
    async def get_task_status(self, task_id, credential) -> VideoTaskStatus
    async def download(self, url, destination) -> None
    async def cancel(self, task_id, credential) -> bool            # 不支持则返回 False
    async def test_connection(self, credential) -> tuple[bool, str]
# providers/llm/base.py
class LLMProvider:
    name: str
    async def generate(self, *, system, prompt, context, model, temperature, max_tokens, credential, base_url=None) -> str
    async def test_connection(self, credential, base_url=None, model=None) -> tuple[bool, str]
```

`MiniMaxVideoProvider`（name=`minimax`）必须严格按以下已核实的官方文档实现（禁止杜撰）：
- base_url 默认 `https://api.minimax.io`（credential 可覆盖，如国内 `https://api.minimaxi.com`）。
- 创建：`POST {base}/v2/video_generation`，Header `Authorization: Bearer <api_key>`，`Content-Type: application/json`。Body：`{"model":"MiniMax-H3","content":[{"type":"text","text":prompt}, ...],"resolution":"768P"|"2K","duration":4..15 int,"ratio":"adaptive"|"21:9"|"16:9"|"4:3"|"1:1"|"3:4"|"9:16"}`。图片项：`{"type":"image_url","image_url":{"url":...},"role":"first_frame"|"last_frame"}`；url 支持公网 URL、`mm_file://{file_id}`、`data:image/<format>;base64,<b64>`。**本地图片文件默认转 data URI**（≤30MB，请求体 ≤64MB，超限报错提示）。
- 规则：t2va（无图）ratio 必填且不能 adaptive（默认 16:9）；有 first/last frame 时 ratio 固定 adaptive；`last_frame` 必须与 `first_frame` 同时出现（单独尾帧不允许——节点 UI/校验提示）。
- 响应：`{"task_id":"..."}`；错误为 OpenAI 风格 `{"type":"error","error":{"type","message","http_code"},"request_id"}`，HTTP 状态即真实错误码。
- 查询：`GET {base}/v2/query/video_generation/{task_id}` → `{"task":{"id","status","content":{"url"},"ratio","duration","resolution","error"?}}`。status ∈ `queued|running|succeeded|failed|cancelled`。
- 取消/删除：`DELETE {base}/v2/video_generation/{task_id}` → `{"task_id","action","status"}`。
- test_connection：调用 List Tasks `GET {base}/v2/query/video_generation?page=1&page_size=1`；401→认证失败；若该端点不存在导致 404，则报告"无法验证（端点不可用）"而不是伪造成功。
- 日志中 API key 一律脱敏为 `sk-****后4位`（core/security.py 提供 `redact()`）。

`OpenAICompatibleLLMProvider`（name=`openai_compatible`）：`POST {base_url}/chat/completions`，body 标准 OpenAI chat 格式；test_connection 用 `GET {base_url}/models`，401/连接错误→失败。credential 需带 base_url 字段。

### 5.4 Credentials

- 表 `credentials`: id(str uuid 短码), name, kind(`llm`|`video`), provider(str), base_url(nullable), secret_encrypted, is_default(bool), created_at, updated_at。
- secret 用 Fernet（cryptography 包）加密；key 来自 env `CREDENTIAL_ENCRYPTION_KEY`，为空则首次启动生成并存 `backend/data/.secret_key`（0600）。
- API 响应只返回 `{id,name,kind,provider,base_url,is_default,masked_secret:"****ab12",created_at}`，绝不返回明文。
- `POST /api/credentials/{id}/test`：按 kind 路由到对应 provider 的 test_connection。
- 节点 config 仅存 `credential_id`。

### 5.5 Workflow Engine（backend/app/workflow/）

- `dag.py`: build_graph(nodes, edges) → 邻接表；`topological_sort`（Kahn）；`detect_cycle`；validate：未知节点类型、缺失必填输入、端口类型不兼容（§2）、重复连接同一单输入口、unknown node id。
- `context.py` `ExecutionContext`: workflow_id, run_id, node_results(dict), variables(dict), output_dir, logger(写 log 表+WS), start_time, cancel_event(asyncio.Event), services（ffmpeg、credentials、http client）、node_output_dir(node_id) 辅助。
- `engine.py`:
  - 校验 → topo 分层（同级无依赖可并行，`asyncio.Semaphore(MAX_CONCURRENCY, 默认2)`）。
  - 节点状态机：`IDLE → QUEUED → (WAITING_CONFIRMATION) → RUNNING → SUCCESS|FAILED|CANCELLED|CACHED`。
  - 每个节点执行前算 cache hash = sha256(json(node_type, version, config（剔除 UI 字段）, resolved_inputs))；命中且 cache 未被清除 → 状态 CACHED，复用 outputs。**inputs 解析自上游 outputs，所以上游变化自然改变 hash**；画布坐标不参与。
  - 失败节点：记录 error，默认策略 `fail_fast=false`——下游依赖它的节点标记 CANCELLED（跳过），无依赖分支继续。
  - cancel_event 设置后：不再调度新节点，未开始的标 CANCELLED；正在跑的节点由节点自身轮询 cancel_event（video 轮询循环每次检查）；远端任务若 provider 支持 cancel 则调用，否则保存 task_id 并日志提示"远端任务可能仍在计费"。
  - `run_from_here(node_id)`：只重跑该节点及下游，上游结果取自最近一次成功 run（node_runs 表）。
  - `resume(run_id)`：新 run 复用旧 run 中 SUCCESS/CACHED 节点的 outputs。
- 所有状态变化、日志通过 `core/events.py` 的内存 EventBus 广播到 `/ws/events`。

### 5.6 数据库表（SQLAlchemy）

- `workflows`: id, name, data(JSON 文本，§4), created_at, updated_at
- `workflow_runs`: id, workflow_id, status(running/success/failed/cancelled/waiting_confirmation), trigger(manual/resume/run_from_here), cost_estimate(JSON), error, started_at, finished_at
- `node_runs`: id, run_id, workflow_id, node_id, node_type, status, inputs(JSON), outputs(JSON), cache_key, provider, model, credential_id, task_id, error, started_at, finished_at
- `tasks`: id, run_id, workflow_id, node_id, provider, model, credential_id, remote_task_id, status, remote_status(JSON), output(JSON), error, created_at, started_at, finished_at
- `credentials`（见 5.4）
- `cache`: id, workflow_id, node_id, cache_key(unique 组合), outputs(JSON), created_at
- `settings`: key, value(JSON)
- `shots`: id, workflow_id, shot_id, title, prompt, optimized_prompt, character_context, scene_context, style_context, input_image, provider, model, task_id, output_video, last_frame, duration, resolution, status, created_at, updated_at（Shot Manager 用；提供 CRUD API）

### 5.7 成本保护（services/cost.py）

`POST /api/workflows/{id}/estimate`：静态分析 workflow JSON → `{paid_node_count, estimated_api_calls, estimated_video_seconds, estimated_cost: null|number, currency:"USD", notes:[...]}`。MiniMax 单价未知时 `estimated_cost=null` 且 notes 含 "Cost unavailable"。settings 支持 `pricing.minimax.per_second`（用户自填，填了就能估算）。运行策略 settings：`require_confirmation(bool, 默认true)`, `max_paid_tasks_per_run(默认20)`, `max_estimated_cost_per_run(默认null)`。超限 → run 创建返回 409 + 原因。`POST /api/workflows/{id}/run` body: `{confirm_paid: bool, resume_from_run_id?, run_from_node_id?}`；含付费节点且 require_confirmation 且未 confirm_paid → 返回 202 `{run_id, status:"waiting_confirmation", estimate}`，前端弹确认框后调 `POST /api/runs/{id}/confirm`。

## 6. REST API（全部 /api 前缀）

```
GET    /api/nodes
GET    /api/templates                      # 内置 workflow 模板（§8）
GET    /api/workflows                      # 列表（id,name,updated_at）
POST   /api/workflows                      # {name,data?}
GET    /api/workflows/{id}
PUT    /api/workflows/{id}                 # {name?,data}
DELETE /api/workflows/{id}
POST   /api/workflows/{id}/duplicate
POST   /api/workflows/{id}/estimate
POST   /api/workflows/{id}/run
GET    /api/runs?workflow_id=
GET    /api/runs/{id}                      # 含 node_runs
POST   /api/runs/{id}/confirm
POST   /api/runs/{id}/stop
POST   /api/runs/{id}/resume
POST   /api/workflows/{id}/nodes/{node_id}/run        # 单节点/Run From Here: body {downstream:bool}
DELETE /api/workflows/{id}/nodes/{node_id}/cache      # Clear Cache
GET    /api/tasks?workflow_id=&status=
GET    /api/tasks/{id}
POST   /api/tasks/{id}/refresh             # 主动查远端状态
POST   /api/tasks/{id}/cancel              # provider 支持才可用
GET    /api/providers                      # [{name,display_name,kind,config_schema}]
GET    /api/credentials?kind=
POST   /api/credentials
PUT    /api/credentials/{id}
DELETE /api/credentials/{id}
POST   /api/credentials/{id}/test
POST   /api/files/upload                   # multipart，存 data/uploads，返回 {path,url,width?,height?}
GET    /api/files/{path:path}              # 安全地伺服 outputs/ 与 data/uploads/ 下的文件
GET    /api/settings ; PUT /api/settings
GET    /api/shots?workflow_id= ; POST/PUT/DELETE /api/shots...
GET    /api/health
```
统一错误：`{"detail": "..."}` + 合适 HTTP 码。所有响应做 secret 脱敏。

## 7. WebSocket `/ws/events`

服务端 → 客户端 JSON：`{"event": "...", "ts": 1234567890, "payload": {...}}`
事件：`workflow.started {run_id,workflow_id}`，`node.queued/node.running/node.waiting_confirmation/node.success/node.failed/node.cached/node.cancelled {run_id,node_id,node_type,error?,outputs?}`，`task.created/task.processing/task.success/task.failed {task_id,node_id,remote_status?}`，`log {run_id,node_id?,level,message}`，`workflow.finished {run_id,status}`，`workflow.cost {run_id,estimate}`。
前端断线自动重连（指数退避，最多 10 次）。

## 8. 内置模板（backend/app/services/templates.py）

`text_to_video`: prompt→prompt_optimizer→video_generation
`image_to_video`: image_input→video_generation
`last_frame_continue`: prompt→optimizer→video_generation→last_frame→(image) video_generation_2（prompt_2→optimizer_2→video_generation_2.prompt）
`three_shot_movie`: 3 条链 → video_merge
`story_to_storyboard`: text→llm→storyboard
模板返回 §4 workflow JSON（带合理坐标）。

## 9. 文件服务与安全

- `GET /api/files/{path}` 只允许访问 `$ROOT/backend/outputs/`、`$ROOT/backend/data/uploads/`、`$ROOT/backend/temp/` 内的文件（resolve 后前缀检查，防目录穿越）。
- 媒体 dict 的 `url` = `/api/files/<相对 outputs 的路径>`。
- 日志、node_runs.inputs/outputs、API 响应里不得出现 credential 明文（config 在入库前剔除/脱敏）。

## 10. Frontend 架构

- `stores/workflowStore.ts`：React Flow 的 nodes/edges + workflowId/name/viewport + dirty；actions: onNodesChange/onEdgesChange/onConnect（**连接时做 §2 类型校验**，非法拒绝并 toast）、addNode/deleteSelection/copy/paste/undo/redo（快照栈，上限 50）、loadWorkflow/saveWorkflow（debounce 1500ms autosave）、applyNodeStatus（WS 驱动）。
- `stores/runStore.ts`：当前 run、nodeStatuses(map node_id→status+error)、logs[]、tasks[]、runs[]。
- `stores/credentialStore.ts`。
- 画布：`@xyflow/react`，自定义 `SchemaNode` 组件：标题栏（icon+name+状态图标+状态文字）、输入 handle 在左、输出在右，**handle 颜色按端口类型**（TEXT 灰/PROMPT 蓝/IMAGE 绿/VIDEO 紫/JSON 黄/…），`connectionRadius`、MiniMap、Controls、Background、框选（selectionOnDrag + panOnDrag=[1,2]）。
- 快捷键：Delete 删选、Ctrl+C/V 复制粘贴（带偏移+新 id）、Ctrl+Z / Ctrl+Shift+Z、Ctrl+S 保存、Space 或双击空白 → 节点搜索面板（模糊搜索+分类分组+键盘上下回车）。
- 左侧 NodeLibrary：按 category 分组（§5.2 的 category），点击/拖拽添加。
- 右侧 PropertiesPanel：选中节点时按 config_schema 动态渲染表单（textarea/number/boolean/select/credential/model/json/file）；`prompt_optimizer` 节点额外显示 Prompt Review 区块：Original / Optimized 对比，按钮 Accept/Edit(可编辑文本域)/Regenerate/Restore Original/Copy（写入 config.edited_prompt）。
- 节点右键 ContextMenu：Run Node / Run From Here / Retry / Clear Cache / Inspect Input / Inspect Output / Delete。
- 底部 BottomPanel Tabs：Logs（搜索+node filter+level filter+复制）、Tasks（表格+Refresh/Cancel/Open Result）、Runs（历史+Resume/Stop）、Cost（estimate 展示+设置链接）。
- Credentials 管理：独立 Dialog/Page，Add/Edit/Delete/Test Connection/Set Default，分 LLM/Video 组。表单绝不回显 secret（编辑时空白=不变）。
- video_preview / video_generation / video_merge 节点内嵌 `<video controls>`；last_frame / frame_extract / image_input 节点内嵌图片预览（所有产出媒体节点自预览，无需挂透传预览节点）。
- 付费确认：点 Run → 先调 estimate → 弹确认框（付费节点数/预估调用/时长/费用或 Cost unavailable）→ confirm 后真正 run。
- 模板菜单：New Blank / New From Template（GET /api/templates）。
- 风格：深色（zinc-950 背景）、专业高密度、类 Linear/VS Code。不要默认蓝紫渐变风。

## 11. 测试（backend/tests/，pytest + pytest-asyncio + httpx MockTransport）

- test_dag.py：topo 排序、环检测、缺输入、类型不兼容。
- test_cache.py：hash 稳定性（坐标变化不改变 hash）、输入变化改变 hash。
- test_nodes.py：prompt 模板渲染、combine_prompt、context 节点、json_parser（含 `$.shots[*].prompt`）、variables。
- test_minimax_provider.py：MockTransport 验证 create/query/cancel 的 URL/body/header、状态映射、错误映射、data URI 生成。
- test_engine.py：用 fake 节点跑并行执行、失败传播、cancel、cache 命中（CACHED）、run_from_here。
- test_credentials.py：加密往返、API 不泄露明文、脱敏格式。
- test_ffmpeg.py：last_frame / merge（用 ffmpeg 生成 1s 测试视频）。
- test_api.py：workflows CRUD、nodes 列表、estimate。

## 12. 其它约定

- requirements.txt：fastapi, uvicorn[standard], sqlalchemy[asyncio]>=2, aiosqlite, pydantic>=2, pydantic-settings, httpx, cryptography, python-multipart, pytest, pytest-asyncio, pytest-mock, jsonpath 不用第三方库（自己实现子集）。
- 所有时间存 ISO 字符串或 unix ts（统一 ISO）。
- logging：backend 同时输出到 stdout 与 `backend/data/server.log`。
- 前端构建必须通过 `npm run build`（tsc 无错）。
- Backend 必须通过 `pytest` 全绿 + `uvicorn app.main:app` 可启动。
