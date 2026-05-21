# Project Montage: Sign Server

FastAPI service that turns a Google Cloud Storage object URI into a time-limited signed URL and immediately redirects the caller.

## Installation

```sh
cd sign_server
uv sync
```

## Configuration

Create a `.env` file (or copy from `.env.example`):

```dotenv
GOOGLE_CLOUD_PROJECT="your-project-id"
SIGNED_URL_EXPIRATION_MINUTES=60
```

| Variable | Purpose |
| --- | --- |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for the storage client |
| `SIGNED_URL_EXPIRATION_MINUTES` | Signed URL expiration time in minutes (default: 60) |


## Behavior

- `GET /view?uri=<bucket>/<object>` returns a 307 redirect to a V4-signed URL using Application Default Credentials.
- Returns 400 for malformed URIs and 500 for unexpected errors.
- `GET /_ah/warmup` is a lightweight health endpoint.

## Deploy

```shell
uv pip freeze --exclude-editable > requirements.txt && \
gcloud app deploy
```

- Requires `gcloud` configured with the target project and an existing App Engine app.

## Notes

- The service only accepts GCS paths in the form `<bucket>/<object>` (no `gs://` prefix).
- The redirect lets clients download without needing direct GCS permissions while keeping object access time-limited.
