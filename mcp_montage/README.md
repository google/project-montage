# MCP Montage Server

The MCP server provides core media generation tools for the Project Montage platform. It orchestrates storyboard creation, image editing, video generation and video stitching using Google's GenAI models (Gemini, Veo, Nano Banana).

## Project Structure

```
mcp_montage/
|── assets               # Assets used by the server
├── server.py            # Main MCP server entry point
├── schemas/             # Pydantic models and data schemas
├── services/            # Core generation services (agents, image, video)
|── shared/              # Shared configurations and constants
├── tools/               # MCP tools exposed to clients
├── utils/               # Helper functions and logging
├── assets/              # Static assets
├── pyproject.toml       # Project dependencies
├── config.yaml          # Model configuration
├── .env                 # Environment variables
└── Dockerfile           # Container configuration
```

## Installation

```sh
cd mcp_montage
bash sync_fonts_from_third_party.sh
uv sync
```

## Configuration

### Environment Variables

Create a `.env` file in this directory:

```dotenv
LOGGING_LEVEL="INFO"
GOOGLE_GENAI_USE_VERTEXAI=False
GOOGLE_CLOUD_PROJECT="your-project"
GOOGLE_CLOUD_LOCATION="global"
# GOOGLE_API_KEY="your-api-key"
GCS_BUCKET_NAME="your-bucket"
GCS_INGREDIENT_IMAGES_FOLDER="gs://your-bucket/ingredient-images"
VIEW_ENDPOINT="http://localhost:8080/view?uri="

# Path to service account JSON (optional, for non-ADC authentication)
# GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
```

| Variable | Purpose |
| --- | --- |
| `LOGGING_LEVEL` | Log verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `GOOGLE_GENAI_USE_VERTEXAI` | Use Vertex AI (`True`) or public API (`False`) |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI region (e.g., `global`) |
| `GOOGLE_API_KEY` | [Optional] API key for public Gemini API (when Vertex is disabled) |
| `GCS_BUCKET_NAME` | GCS bucket for media storage |
| `GCS_INGREDIENT_IMAGES_FOLDER` | [Optional] GCS path for ingredient/character images |
| `VIEW_ENDPOINT` | [Optional] Sign server URL for generating viewable links |
| `GOOGLE_APPLICATION_CREDENTIALS` | [Optional] Path to service account JSON |

### Model Configuration

Customize GenAI models in `config.yaml`:

```yaml
# Text generation (storyboard, prompts)
gemini_model: gemini-3.1-flash-lite

# Image generation and editing
gemini_image_model: gemini-2.5-flash-image

# Video generation
veo_model: veo-3.1-generate-001
```

### Agent Prompts

The agent prompts are located in `services/agents/config/`:

| Folder | Purpose |
| --- | --- |
| `core_prompt/` | **Core Agent logic**. This contains the fundamental instructions for the agents and should not be modified. |
| `specific_prompt/` | **Project Montage customization**. Use this to edit, add capabilities, or define limitations specific to the Project Montage project. |

## MCP Tools

| Tool | Description |
| --- | --- |
| `select_asset` | Select the most suitable asset image based on the provided user context using Gemini. |
| `generate_storyboard` | Generates a video storyboard consisting of multiple scenes based on user context. |
| `generate_image` | Generates images from text prompts using Gemini |
| `generate_video` | Generates video clips from images using Veo |
| `concatenate_videos` | Merges video clips into a single sequence |
| `generate_bgm_and_merge` | Generates background music and merges with video |
| `generate_scene_narratives` | Generates a narration script (SRT) for a video scene using Gemini |

## GCS Folder Structure

| Folder | Purpose |
| --- | --- |
| `user_uploads/` | User-uploaded images for scene generation |
| `generated_images/` | Generated/edited storyboard images |
| `generated_videos/` | Individual scene video clips |
| `concatenated_videos/` | Combined video sequences |
| `videos_with_bgm/` | Final videos with background music |

## Running Locally

```sh
# With uv
uv run uvicorn server:app --port 8001 --reload

# Or after activating the virtual environment
uvicorn server:app --port 8001 --reload
```

The server will be available at `http://localhost:8001`.

## Deployment

### Docker

```sh
bash sync_fonts_from_third_party.sh
docker build -t mcp-montage .
docker run -p 8001:8001 --env-file .env \
  -v "$APPDATA/gcloud/application_default_credentials.json:/tmp/keys/creds.json" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
  mcp-montage
```