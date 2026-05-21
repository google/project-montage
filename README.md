# README.md (English Version)

<p align="right"><strong>English</strong> | <a href="README_zh-CN.md">简体中文</a></p>

# 🎬 Project Montage

## 📖 What is Project Montage?

**Project Montage** is a modular, AI-powered video builder that enables developers to rapidly create fully edited, production-quality videos directly from code. Built on Google's advanced generative AI ecosystem—powered by Gemini's orchestration capabilities and integrated with Veo and Nano Banana models—it transforms a simple storyboard outline into a cohesive narrative video, complete with cinematic clips, transitions, and generative music.

## 💡 Why Use Project Montage?

Video production with multiple AI models often involves complex orchestration and fragmented workflows. Project Montage addresses this by providing a unified, agentic pipeline that automates the entire creative lifecycle. Here are the key benefits:

- **Unrivaled Flexibility & Seamless Enterprise Data Integration:** Streamline internal data into high-volume marketing video production.
- **Multi-Agent Synergy & High-Fidelity Content Output:** Create cinema-quality, natively synced videos using Google's premier AI models (Nano Banana, Veo).
- **Open-Source Infrastructure for Rapid, Ready-to-Deploy Implementation:** Deploy a ready-to-use framework instantly while retaining technical independence.

## ☁️ Environment Setup (GCP Optimized)

Project Montage is designed with a highly modular multi-agent framework. While you can modify the code to integrate other third-party services, the project is optimized for Google Cloud Platform (GCP) out-of-the-box, leveraging powerful models like Gemini and Veo for the smooth experience.
We highly recommend setting up GCP to get your first video running smoothly.

### 1. Set up your Google Cloud Project

- Go to the [Google Cloud Console](https://console.cloud.google.com/).
- Create a new project or select an existing one.
- **Important:** Ensure that **Billing is enabled** for your Cloud project to use Vertex AI.

### 2. Enable Required APIs

Navigate to Vertex AI in the console and click "Enable All Recommended APIs," or run the following in your terminal:

```sh
gcloud services enable aiplatform.googleapis.com
```

### 3. Configure Local Authentication

For local development, use Application Default Credentials (ADC). Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) if you haven't already, then run:

```sh
# Login with your Google account
gcloud auth application-default login

# Set your active project
gcloud config set project <YOUR_PROJECT_ID>
```

## 🚀 Quick Start

Get your first video generated in minutes. After cloning the repository, set up and run the core services in three separate terminals:

```sh
# First, clone the project
git clone https://github.com/google/project-montage.git
cd project-montage

# --- Terminal 1: Start the MCP Server ---
cd mcp_montage
uv sync
bash sync_fonts_from_third_party.sh
cp .env.example .env # Edit .env with your configuration
uv run uvicorn server:app --port 8001 --reload

# --- Terminal 2: Start the MCP Client (Web UI) ---
cd mcp_client
uv sync
cp .env.example .env # Edit .env with your configuration
uv run uvicorn server:app --port 8000 --reload

# --- Terminal 3: Start the Sign Server ---
cd sign_server
uv sync
cp .env.example .env # Edit .env with your configuration
uv run uvicorn server:app --port 8080
```

Once running, open the ADK Web UI in your browser to orchestrate the video production workflow!

## ✨ Core Features

- **AI-Powered Orchestration:** A central agent powered by Gemini interprets your creative outline and automatically assigns tasks to specialized agents.
- **Multi-Agent Architecture:**
  - **Storyboard Generation:** Automatically drafts a scene-by-scene plan and selects optimal input images.
  - **Intelligent Asset Selection:** Automatically decides which input images best match generated scene descriptions.
  - **Cinematic Video Generation:** Leverages Google's **Veo 3.1** model to create high-quality, dynamic video clips.
  - **Character Integration:** Uses Nano Banana for consistent character integration and asset resizing.
- **Automated Post-Production:** Seamlessly stitches clips together with professional transitions and generative background music aligned to the content theme.

## 📺 Demo

_(See Montage in action! Orchestrates multi-agent workflows to transform a storyboard outline into a fully-edited, professional video.)_

## 🤝 Contributing

We welcome contributions! Please set up the environment using the following steps:

```sh
# Set up pre-commit hooks
pip install pre-commit && pre-commit install

# Lint and Format with Ruff
uvx ruff check .
uvx ruff format .

# Run Tests
pytest tests/
```

Please open an issue first to discuss any significant changes before submitting a Pull Request.
