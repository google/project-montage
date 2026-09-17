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
GCS_BUCKET_NAME="your-bucket-name"
SIGNED_URL_EXPIRATION_MINUTES=60
```

| Variable | Purpose |
| --- | --- |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for the storage client |
| `GCS_BUCKET_NAME` | The only bucket whose objects are signed (required) |
| `SIGNED_URL_EXPIRATION_MINUTES` | Signed URL expiration time in minutes (default: 60) |


## Behavior

- `GET /view?uri=<bucket>/<object>` returns a 307 redirect to a V4-signed URL using Application Default Credentials.
- Returns 400 for malformed URIs, 403 for objects outside `GCS_BUCKET_NAME`, and 500 when `GCS_BUCKET_NAME` is unset or signing fails.

## Tests

```sh
uv run pytest
```

## Deploy

The sign server runs on Cloud Run and is deployed by the repository-wide
script. See [deploy/README.md](../deploy/README.md).

```sh
./deploy/deploy.sh setup --env dev          # first time, with the sign server enabled
./deploy/deploy.sh --env dev --only sign    # later updates
```

Its service account needs `roles/iam.serviceAccountTokenCreator` on itself to sign through the IAM API; `setup` grants it.

## Notes

- The service only accepts GCS paths in the form `<bucket>/<object>` (no `gs://` prefix).
- The redirect lets clients download without needing direct GCS permissions while keeping object access time-limited.
