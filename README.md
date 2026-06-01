# Skill Chat

基于 AI 的技能提取与对话平台。将电子书（EPUB）自动解析为结构化技能集合，并提供多模型 AI 对话能力。

## 功能概览

- **AI 对话**：支持多模型切换的智能对话，可关联技能包增强回答质量
- **书籍技能提取**：上传 EPUB 电子书，自动解析 → 概览分析 → 深度提取 → 去重验证 → 关联映射 → 生成结构化技能包
- **技能包管理**：私有/公开可见性控制、技能包广场浏览与复制
- **会话管理**：对话历史的创建、查看、删除与持久化存储
- **用户体系**：注册/登录/会话管理、管理员角色与权限控制
- **管理后台**：用户管理、任务监控、技能包审核、数据统计

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Starlette + Uvicorn (ASGI) |
| AI 框架 | pydantic-ai (Agent + VercelAIAdapter) |
| 技能提取 | LangGraph (状态图) + LangChain (LLM 调用) |
| 数据库 | SQLite (WAL 模式) |
| 前端 | React + TypeScript + Vite (ai-chat-ui) |
| 文档解析 | Pandoc (EPUB → Markdown) |
| 部署 | Docker / Docker Compose |

## 项目结构

```
skill-chat/
├── app/                        # 核心应用包
│   ├── __init__.py             # 入口：uvicorn 启动
│   ├── __main__.py             # python -m app 入口
│   ├── config.py               # 路径与端口配置
│   ├── server.py               # HTTP 路由与服务组装
│   ├── auth/                   # 认证模块
│   │   ├── crypto.py           # 密码哈希、会话令牌、异常定义
│   │   └── service.py          # 注册/登录/登出/权限校验
│   ├── chat/                   # 对话模块
│   │   ├── models.py           # AI 模型注册表
│   │   └── agent.py            # Agent 构建与 Skill 发现
│   ├── store/                  # 数据存储层
│   │   ├── base.py             # SQLite 连接管理与 Schema
│   │   ├── user.py             # 用户与会话 CRUD
│   │   ├── conversation.py     # 对话与消息 CRUD
│   │   ├── task.py             # 技能提取任务 CRUD
│   │   ├── skill_pack.py       # 技能包 CRUD
│   │   └── admin.py            # 管理后台聚合查询
│   └── task/                   # 任务管理
│       └── manager.py          # 技能提取任务生命周期
├── book2skill_agent/           # 技能提取引擎 (独立包)
│   ├── agent.py                # LangGraph 状态图定义
│   ├── config.py               # API 配置与路径
│   ├── parser.py               # EPUB/PDF 文档解析
│   ├── service.py              # 服务层：任务执行与归档
│   ├── skill_markdown.py       # 技能 Markdown 生成与校验
│   └── token_tracker.py        # Token 使用量追踪
├── book2skill/                 # 提取器提示词与模板
│   ├── extractors/             # 各类提取器 Prompt
│   └── templates/              # 技能 Markdown 模板
├── ai-chat-ui/                 # 前端源码 (React)
├── web/                        # 前端构建产物 (静态文件)
├── tools/                      # 可用工具定义
├── skills/                     # 生成的技能包目录
├── books/                      # 书籍解析输出目录
├── data/                       # 运行时数据
│   ├── app.db                  # SQLite 数据库
│   ├── uploads/                # 上传的 EPUB 文件
│   └── archives/               # 技能包压缩归档
├── Dockerfile                  # Docker 镜像定义
├── docker-compose.yml          # Docker Compose 编排
└── requirements.txt            # Python 依赖
```

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

服务将在 `http://localhost:8000` 启动。

### 方式二：本地运行

**前置要求：**
- Python 3.12+
- Pandoc（用于 EPUB 解析）
- pnpm（用于前端构建）

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 构建前端（首次或前端代码变更时）
cd ai-chat-ui
pnpm install
pnpm run build
cd ..

# 启动服务
python -m app
```

服务将在 `http://0.0.0.0:8000` 启动。

### 恢复管理员账号

如果数据库中无用户，首个注册的账号自动成为管理员。如需手动恢复：

```bash
python restore_admin.py
```

## 核心流程

### 技能提取流程

```
EPUB 上传 → Parser 解析 → Overview 概览分析 → Extract 深度提取
    → Verify 两阶段验证 → Relate 关联映射 → RIA 技能封装 → Index 索引生成
```

LangGraph 状态图采用条件边，任一节点失败时自动终止并记录错误。

### AI 对话流程

```
用户消息 → 选择模型 → 加载关联技能包 → 构建 Agent → 流式响应
```

## API 接口

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET  | `/api/auth/me` | 当前用户信息 |

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送消息（SSE 流式） |
| GET  | `/api/conversations` | 会话列表 |
| POST | `/api/conversations` | 创建会话 |
| GET  | `/api/conversations/{id}/messages` | 获取消息 |
| POST | `/api/conversations/{id}/messages` | 保存消息 |
| DELETE | `/api/conversations/{id}` | 删除会话 |

### 技能包

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/skill-packs` | 所有可见技能包 |
| GET  | `/api/skill-packs/mine` | 我的技能包 |
| DELETE | `/api/skill-packs/{id}` | 删除技能包 |
| POST | `/api/skill-packs/{id}/visibility` | 修改可见性 |

### 技能任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/skill-tasks` | 任务列表 |
| POST | `/api/skill-tasks` | 创建任务（上传 EPUB） |
| GET  | `/api/skill-tasks/{id}` | 任务详情 |
| GET  | `/api/skill-tasks/{id}/events` | 任务事件 |
| GET  | `/api/skill-tasks/{id}/events/stream` | SSE 事件流 |
| GET  | `/api/skill-tasks/{id}/archive` | 下载技能包 |
| DELETE | `/api/skill-tasks/{id}` | 删除任务 |

### 广场

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/plaza/skill-packs` | 公开技能包 |
| POST | `/api/plaza/skill-packs/{id}/copy` | 复制到我的库 |

### 管理后台

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/admin/overview` | 系统统计 |
| GET  | `/api/admin/users` | 用户列表 |
| PATCH | `/api/admin/users/{id}` | 更新用户状态 |
| GET  | `/api/admin/tasks` | 所有任务 |
| DELETE | `/api/admin/tasks/{id}` | 删除任务 |
| GET  | `/api/admin/conversations` | 所有会话 |
| DELETE | `/api/admin/conversations/{id}` | 删除会话 |
| GET  | `/api/admin/skill-packs` | 所有技能包 |
| POST | `/api/admin/skill-packs/{id}/visibility` | 修改可见性 |

## 配置说明

配置集中在以下文件中，无需环境变量：

- **`app/config.py`** — 服务端口、数据目录、前端产物路径
- **`app/chat/models.py`** — AI 模型配置（API 地址、密钥、模型名称、系统提示词）
- **`book2skill_agent/config.py`** — 技能提取 LLM API 地址、模型名称、Prompt 目录

## 数据持久化

Docker 部署时，以下目录通过 volume 挂载到宿主机：

- `./data` — SQLite 数据库、上传文件、归档文件
- `./books` — 书籍解析与技能提取输出
- `./skills` — 技能包文件目录

## 开源引用

书籍处理流程参考了开源项目 [cangjie-skill](https://github.com/kangarooking/cangjie-skill)，该项目提出了 RIA-TV++ 方法论，将书籍中的方法论蒸馏为可被 AI Agent 调用的结构化技能包。`book2skill/` 目录下的提取器、方法论与模板均源自该项目。
