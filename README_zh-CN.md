# README_zh-CN.md (Chinese Version)

<p align="right"><a href="README.md">English</a> | <strong>简体中文</strong></p>

# 🎬 Project Montage: 蒙太奇

## 📖 简介

**Project Montage** 是一个模块化、AI驱动的视频构建框架，旨在助力开发者通过代码快速构建具备生产级质量的视频自动化工作流。

该框架基于 Google 先进的生成式 AI 生态构建，依托 Gemini 的智能体编排能力，协同 Veo 与 Nano Banana 模型，能将故事大纲自动转化为具有电影质感的连贯叙事视频——自动完成剪辑、转场、角色插入及背景音乐合成。它能将简单的故事大纲自动转化为带有电影级运镜、转场特效和生成式配乐的高质量叙事视频。

## 💡 为什么选择 Montage?

使用多款 AI 模型进行视频创作，往往涉及复杂的模型编排与碎片化的工作流。Project Montage 通过统一的智能体 (Agentic) 流水线将这些流程简化，实现全流程自动化。以下是它的核心优势：

- **高度灵活性与企业数据集成：** 高效对接内部数据源，打破工具孤岛，让视频生产流水线能够随着业务需求弹性伸缩，助力规模化营销视频生产。
- **多模型协同与高保真输出：** 融合 Nano Banana 与 Veo 模型能力，实现高保真、多模态同步的影视级内容产出。
- **开源架构与即插即用：** 提供高度模块化的开源参考架构。无需复杂的环境配置，开箱即用，在确保企业级基础设施自主可控的前提下，实现业务的极速部署。

## ☁️ 准备工作：环境配置 (推荐使用 GCP)

Project Montage 拥有高度模块化的多智能体架构。虽然您完全可以通过修改少量代码来接入其他的云存储或大模型服务，但本项目原生针对 Google Cloud (GCP) 进行了深度优化，开箱即可调用 Gemini 和 Veo 等领先模型。

为了获得顺畅的“一键出片”体验，我们强烈建议您初始阶段使用 GCP 环境。

### 💡 针对出海开发者的贴心提示 (Tips)

- **网络环境：** 在终端运行 gcloud 相关命令时，请确保您的终端环境已正确配置了全局代理。
- **云资源结算：** 调用 Vertex AI 高级模型需要开启结算 (Billing) 账户。

### 1. 创建 GCP 项目与开启计费

- 访问 [Google Cloud Console](https://console.cloud.google.com/).
- 创建一个新项目或选择现有项目。
- **务必确保**该项目已经绑定了有效的结算账户。

### 2. 开启必要的 API

在 Vertex AI 界面点击"开启所有建议的 API"，或在终端执行：

```sh
gcloud services enable aiplatform.googleapis.com
```

### 3. 本地环境鉴权 (Authentication)

在本地开发时，最便捷的方式是使用应用默认凭据 (ADC)。安装 [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) 后运行：

```sh
# 登录你的谷歌账号
gcloud auth application-default login

# 设置你刚刚创建的 GCP 项目 ID
gcloud config set project <YOUR_PROJECT_ID>
```

## 🚀 快速上手 (Quick Start)

只需几分钟，跑通你的第一个视频流！克隆代码库后，在三个独立的终端窗口分别启动服务：

```sh
# 首先，克隆项目并进入目录
git clone https://github.com/google/project-montage.git
cd project-montage

# --- 终端 1: 启动 MCP 后端服务 ---
cd mcp_montage
uv sync
bash sync_fonts_from_third_party.sh
cp .env.example .env # 记得填入你的环境变量
uv run uvicorn server:app --port 8001 --reload

# --- 终端 2: 启动 MCP 客户端 (Web UI) ---
cd mcp_client
uv sync
cp .env.example .env # 记得填入你的环境变量
uv run uvicorn server:app --port 8000 --reload

# --- 终端 3: 启动 签名服务 (Sign Server) ---
cd sign_server
uv sync
cp .env.example .env # 记得填入你的环境变量
uv run uvicorn server:app --port 8080
```

服务启动后，访问 ADK Web UI 即可开始编排你的视频生产流程！

## ✨ 核心功能 (Features)

- **🧠 AI 原生编排：** 基于 Gemini 的中心调度 Agent 能够理解创意大纲，并自动分发任务给专业 Agent。

- **🤖 多智能体架构 (Multi-Agent)：**
  - **分镜生成 (Storyboard)：** 自动将 Prompt 拆解为分镜，并基于描述智能匹配输入图片。
  - **资产精选：** 自动决策并选择最契合场景的视觉资产。
  - **电影级视频生成：** 集成 Google **Veo 3.1** 模型，生成动感十足的高清视频片段。
  - **角色一致性：** 利用 Nano Banana 实现一致的角色整合和资产缩放。
- **🎞️ 自动化后期：**  无缝拼接视频片段，自动添加平滑转场和契合情绪的生成式配乐。

## 📺 视觉展示 (Demo)

_百闻不如一见，看看 Montage 是如何通过多智能体编排一键出片的：_

## 🤝 参与贡献 (Contributing)

我们欢迎开发者参与共建！提交 PR 前请进行代码质量检查：

```sh
# 安装 pre-commit hooks
pip install pre-commit && pre-commit install

# 使用 Ruff 进行代码检查和格式化
uvx ruff check .
uvx ruff format .

# 运行单元测试
pytest tests/
```

遇到 Bug 或有新想法，请先提交 Issue 讨论。
