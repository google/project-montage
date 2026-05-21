# MCP Client

The MCP client provides an ADK-based web interface for interacting with the Project Montage MCP server. It features an `OrchestratorAgent` that orchestrates the video production workflow by calling MCP server tools.

## Project Structure

```
mcp_client/
├── adk/                 # ADK web application
│   └── project_montage/ # OrchestratorAgent implementation
├── frontend/            # Landing page assets
├── shared/              # Shared utilities and constants
├── utils/               # Client-side utility functions
├── pyproject.toml       # Project dependencies
├── .env                 # Environment variables
├── Dockerfile           # Container configuration
└── app.yaml             # App Engine configuration
```

## Installation

```sh
cd mcp_client
uv sync
```

## Configuration

### Environment Variables

Create a `.env` file in this directory (or copy from `.env.example`):

```dotenv
LOGGING_LEVEL="INFO"
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_CLOUD_LOCATION="global"
# GOOGLE_API_KEY="your-api-key"
GCS_BUCKET_NAME="your-bucket-name"

# ADK Session Service (Postgres, optional)
# DB_CONNECTION_NAME="your-project:your-region:your-instance"
# SESSION_SERVICE_URI="postgresql+asyncpg://postgres:password@/postgres?host=/cloudsql/${DB_CONNECTION_NAME}"

# MCP Server Connection
SERVER_CONNECTION_TYPE="http"
SERVER_URL="http://localhost:8001"
```

| Variable | Purpose |
| --- | --- |
| `LOGGING_LEVEL` | Log verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `GOOGLE_GENAI_USE_VERTEXAI` | Use Vertex AI (`True`) or public API (`False`) |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID (required for Vertex AI) |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI region (e.g., `global`) |
| `GOOGLE_API_KEY` | [Optional] API key (when Vertex is disabled) |
| `GCS_BUCKET_NAME` | GCS bucket for media storage |
| `DB_CONNECTION_NAME` | [Optional] Cloud SQL database connection name |
| `SESSION_SERVICE_URI` | [Optional] ADK session storage URI |
| `SERVER_CONNECTION_TYPE` | MCP connection type: `stdio` (local), `sse` (SSE), or `http` (Streamable HTTP) |
| `SERVER_URL` | MCP server URL (e.g. `http://localhost:8001`) |

## Running Locally

```sh
# With uv
uv run uvicorn server:app

# Or after activating the virtual environment
uvicorn server:app
```

The web interface will be available at `http://localhost:8000`.

## Deployment

### Docker

```sh
docker build -t mcp-client .
docker run -p 8000:8000 --env-file .env mcp-client
```
