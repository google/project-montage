# Project Montage Onboarding

This guide walks through GCP onboarding, local development, and the guided GCP setup command for Project Montage:

1. Create and configure a Google Cloud project.
2. Enable the Agent Platform API and configure Cloud Storage.
3. Authenticate locally with Application Default Credentials.
4. Install the project dependencies.
5. Configure the local environment.
6. Switch between deploying to GCP and running locally.

Build and deployment instructions are intentionally omitted for now.

## 1. What runs locally

Project Montage is made up of two local services:

| Service     | Purpose                                                                | Local address         |
| ----------- | ---------------------------------------------------------------------- | --------------------- |
| mcp_montage | MCP server for image, video, audio, storage, and post-production tools | http://localhost:8001 |
| mcp_client  | ADK-based web interface and orchestration agent                        | http://localhost:8000 |

The MCP server and web client are required for the normal local workflow.

## 2. Prerequisites

Install or prepare the following:

- A Google Account with access to the Google Cloud Console.
- An active Google Cloud Billing account.
- [Git](https://git-scm.com/downloads).
- [Python 3.13 or later](https://www.python.org/downloads/). The services declare a minimum Python version of 3.13.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for Python environment and dependency management.
- The [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
- A Bash-compatible shell for the font synchronization script. On Windows, use Git Bash or WSL for that one step.

Check the local tool versions:

~~~sh
git --version
python --version
uv --version
gcloud --version
~~~

## 3. Create and configure the Google Cloud project

### 3.1 Create or select a project

Use a separate project for local development so billing, quotas, IAM permissions, and generated assets are isolated from unrelated workloads.

#### Google Cloud Console

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Open the project selector in the top navigation bar.
3. Click **New Project**.
4. Enter a project name, for example **project-montage-dev**.
5. If your account belongs to an organization, select the appropriate **Organization** and **Location**.
6. Click **Create**.
7. Select the new project from the project selector.
8. Copy the **Project ID** from **Home > Project info**. Use this ID—not the display name—in environment variables and CLI commands.

If you already have a suitable project, select it and record its Project ID.

#### Google Cloud CLI

Choose a globally unique project ID:

~~~sh
gcloud projects create <YOUR_PROJECT_ID> --name="Project Montage"
gcloud config set project <YOUR_PROJECT_ID>
~~~

If project creation fails, your account needs the **Project Creator** role (roles/resourcemanager.projectCreator), or an administrator must create the project for you.

### 3.2 Link billing

Billing is required for many Google Cloud services and for billable model and storage usage.

In the console:

1. Open the project selector in the top navigation bar and select **project-montage-dev**.
2. Open the navigation menu in the top-left corner.
3. Select **Billing**.
4. If **project-montage-dev** is not linked to a billing account, choose the option to **Link a billing account**.
5. Select an existing billing account, or create a new billing account if you do not have one.
6. Confirm that **project-montage-dev** is linked to an active billing account.

From the CLI, list the billing accounts available to your account and link one to the project:

~~~sh
gcloud billing accounts list

gcloud billing projects link <YOUR_PROJECT_ID> \
  --billing-account=<BILLING_ACCOUNT_ID>
~~~

Confirm the link:

~~~sh
gcloud billing projects describe <YOUR_PROJECT_ID>
~~~

Billing linking requires access to both the project and the target billing account. In an organization-managed account, ask a billing administrator to complete this step if necessary.

### 3.3 Enable the Agent Platform API

Project Montage uses Google's **Agent Platform** for Gemini, Veo, Nano Banana, and Lyria requests. Some documentation and SDK environment variables still use **Vertex AI**, which is the older product name. The underlying API service for this setup is:

~~~text
aiplatform.googleapis.com
~~~

#### Google Cloud Console

1. Make sure the Project Montage project is selected.
2. Open **APIs & Services > Library**.
3. Search for **Agent Platform API**.
4. If the result is labeled **Vertex AI API**, verify that its service name is aiplatform.googleapis.com.
5. Open the API details page and click **Enable**.
6. Open **APIs & Services > Enabled APIs & services** and confirm that the API is enabled.

Open the API directly from the [Agent Platform API page](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com).

#### Google Cloud CLI

~~~sh
gcloud services enable aiplatform.googleapis.com \
  --project=<YOUR_PROJECT_ID>
~~~

Verify that it is enabled:

~~~sh
gcloud services list --enabled \
  --project=<YOUR_PROJECT_ID> \
  --filter="config.name=aiplatform.googleapis.com"
~~~

Enabling an API requires the serviceusage.services.enable permission. Project Owners generally have this permission. Otherwise, ask an administrator for the **Service Usage Admin** role (roles/serviceusage.serviceUsageAdmin).

### 3.4 Create a Cloud Storage bucket

Project Montage uses Cloud Storage for uploaded ingredients and generated media. The bucket name must be globally unique.

#### Google Cloud Console

1. Open **Cloud Storage > Buckets** and click **Create**.
2. Enter a globally unique bucket name, such as **project-montage-<UNIQUE_SUFFIX>**.
3. Choose a location near your users. A single region is a good choice for local development.
4. Keep **Uniform bucket-level access** enabled.
5. Keep **Public access prevention** enabled.
6. Create the bucket.
7. Record the bucket name without the gs:// prefix; this is the value used for GCS_BUCKET_NAME.

#### Google Cloud CLI

Enable the Cloud Storage API and create the bucket:

~~~sh
gcloud services enable storage.googleapis.com \
  --project=<YOUR_PROJECT_ID>

gcloud storage buckets create gs://<YOUR_BUCKET_NAME> \
  --project=<YOUR_PROJECT_ID> \
  --location=<BUCKET_LOCATION> \
  --public-access-prevention \
  --uniform-bucket-level-access
~~~

### 3.5 Grant IAM access

The Google Account used by the local services needs permission to call Agent Platform models and access the bucket.

Grant **Agent Platform User** on the project:

~~~sh
gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
  --member="user:<YOUR_GOOGLE_ACCOUNT_EMAIL>" \
  --role="roles/aiplatform.user"
~~~

Grant **Storage Object Admin** on the bucket. This allows the local workflow to upload, read, update, and delete generated assets:

~~~sh
gcloud storage buckets add-iam-policy-binding gs://<YOUR_BUCKET_NAME> \
  --member="user:<YOUR_GOOGLE_ACCOUNT_EMAIL>" \
  --role="roles/storage.objectAdmin"
~~~

If your account is already the project Owner, you may inherit enough access for local testing. For shared or production-like projects, use narrower roles and ask an administrator to grant them.

## 4. Configure local authentication

Project Montage uses [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/provide-credentials-adc) when GOOGLE_GENAI_USE_VERTEXAI=True.

Initialize the Google Cloud CLI, sign in, and select the project:

~~~sh
gcloud init
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>
gcloud auth application-default set-quota-project <YOUR_PROJECT_ID>
~~~

The ADC command opens a browser. Authorize the same Google Account that has the Agent Platform and Cloud Storage roles above.
Setting the ADC quota project helps Google APIs associate local development requests with the correct project for quota and billing.

Verify the active project and credentials:

~~~sh
gcloud config get-value project
gcloud auth list
gcloud auth application-default print-access-token
~~~

Do not commit ADC files, service-account keys, or API keys to the repository.

## 5. Clone the repository

If you have not cloned the repository yet:

~~~sh
git clone https://github.com/google/project-montage.git
cd project-montage
~~~

If the repository is already present, open a terminal at its root directory.

## 6. Choose a setup path

After cloning the repository, choose a path below. You can switch between Path A and Path B at any time.

### Path A: Deploy to GCP

From the repository root, run the setup command in Bash, Git Bash, WSL, macOS, or Linux:

~~~sh
./deploy/deploy.sh setup --env dev
~~~

The command opens the interactive onboarding CLI. Follow its prompts for the Google Cloud project, region, Agent Platform location, Artifact Registry repository, and Cloud Storage bucket. It also offers optional setup for Cloud SQL, the sign server, and web access controls.

The CLI creates or verifies the required GCP resources and saves the answers in deploy/config/dev.env. If it asks whether to run the first deploy, choose **No** for now. Build and deployment instructions will be documented separately.

### Path B: Run locally

Continue with Steps 7–10 below to install dependencies, configure the local environment, run the MCP server and web client, and stop the local services.

## 7. Install dependencies

Each service has its own pyproject.toml and virtual environment managed by uv.

### MCP server

Run these commands from the root directory:

~~~sh
cd mcp_montage
uv sync
bash sync_fonts_from_third_party.sh
~~~

The font script copies assets from third_party/fonts into mcp_montage/assets/fonts. Run it from mcp_montage, not from the repository root.

### MCP client

~~~sh
cd ../mcp_client
uv sync
~~~

Return to the repository root when needed:

~~~sh
cd ..
~~~

On Windows, run the bash sync_fonts_from_third_party.sh command in Git Bash or WSL. The other uv and application commands can be run from PowerShell, Command Prompt, Git Bash, or WSL.

## 8. Configure environment files

Copy the example files:

### macOS, Linux, or Git Bash

~~~sh
cp mcp_montage/.env.example mcp_montage/.env
cp mcp_client/.env.example mcp_client/.env
~~~

### PowerShell

~~~powershell
Copy-Item mcp_montage/.env.example mcp_montage/.env
Copy-Item mcp_client/.env.example mcp_client/.env
~~~

### 8.1 MCP server environment

Edit mcp_montage/.env:

~~~dotenv
LOGGING_LEVEL="INFO"
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT="<YOUR_PROJECT_ID>"
GOOGLE_CLOUD_LOCATION="global"
GCS_BUCKET_NAME="<YOUR_BUCKET_NAME>"
GCS_INGREDIENT_IMAGES_FOLDER="gs://<YOUR_BUCKET_NAME>/ingredient-images"
~~~

### 8.2 MCP client environment

Edit mcp_client/.env:

~~~dotenv
LOGGING_LEVEL="INFO"
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT="<YOUR_PROJECT_ID>"
GOOGLE_CLOUD_LOCATION="global"
GCS_BUCKET_NAME="<YOUR_BUCKET_NAME>"

SERVER_CONNECTION_TYPE="http"
SERVER_URL="http://localhost:8001"
~~~

SERVER_URL must point to the locally running MCP server. Keep SERVER_CONNECTION_TYPE="http" for the default local setup.

The ADK session service is optional for local startup. If you need persistent sessions, configure SESSION_SERVICE_URI with a PostgreSQL connection string as described in mcp_client/.env.example.

## 9. Run Project Montage locally

Start each service in its own terminal. Start the MCP server first so the client can connect to it.

### Terminal 1: MCP server

~~~sh
cd project-montage/mcp_montage
uv run uvicorn server:app --host 127.0.0.1 --port 8001 --reload
~~~

The MCP server exposes:

- http://localhost:8001/version for a version check.
- http://localhost:8001/mcp for Streamable HTTP MCP connections.
- http://localhost:8001/sse for SSE MCP connections.

### Terminal 2: MCP client and web UI

~~~sh
cd project-montage/mcp_client
uv run uvicorn server:app --host 127.0.0.1 --port 8000 --reload
~~~

Open [http://localhost:8000](http://localhost:8000) in a browser.

### Quick local checks

From PowerShell:

~~~powershell
Invoke-WebRequest http://localhost:8001/version
Invoke-WebRequest http://localhost:8000
~~~

From macOS, Linux, Git Bash, or WSL:

~~~sh
curl http://localhost:8001/version
curl http://localhost:8000
~~~

Open http://localhost:8000 in your browser to load the Project Montage web interface. The client connects to the MCP server at http://localhost:8001.

## 10. Stop the local services

In each service terminal, press Ctrl+C. If you used --reload, stop the reloader process as well if it remains active.

## Troubleshooting

### Permission denied or 403 from Agent Platform

Confirm all of the following:

- The active project is the intended Project Montage project.
- Billing is enabled and the billing account is active.
- aiplatform.googleapis.com is enabled.
- The authenticated account has roles/aiplatform.user.
- GOOGLE_CLOUD_PROJECT matches the project where the API is enabled.

### Cloud Storage permission errors

Confirm that:

- GCS_BUCKET_NAME contains only the bucket name, without gs://.
- The bucket exists in the selected project.
- The authenticated account has access to the bucket, such as roles/storage.objectAdmin for local development.

### ADC authentication errors

Run gcloud auth application-default login again and make sure the browser login uses the account that has the required project roles. gcloud auth login and ADC are separate credential stores; logging into one does not always configure the other.

### The MCP client cannot connect

Check that:

- The MCP server is running on port 8001.
- SERVER_CONNECTION_TYPE="http".
- SERVER_URL="http://localhost:8001".
- The MCP server terminal has no startup exception.

### Font synchronization fails

Run bash sync_fonts_from_third_party.sh from the mcp_montage directory using Git Bash or WSL. Confirm that the repository contains third_party/fonts.

### The MCP server starts slowly or uses too much memory

The server warms up a forced-alignment model at startup. To skip that warm-up for local development, add this to mcp_montage/.env:

~~~dotenv
WARM_UP_FORCED_ALIGNMENT=false
~~~

The first request that needs the skipped capability may take longer.

## References

- [Google Cloud project creation](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
- [Cloud Billing project setup](https://cloud.google.com/billing/docs/how-to/modify-project)
- [Agent Platform API reference](https://cloud.google.com/gemini-enterprise-agent-platform/reference/rest)
- [Google Cloud CLI installation](https://cloud.google.com/sdk/docs/install)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc)
- [Cloud Storage bucket creation](https://cloud.google.com/storage/docs/creating-buckets)
