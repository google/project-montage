# Deployment

One script deploys Project Montage to Google Cloud Run: an interactive
`setup` for the first time, and a one-line deploy for every release after.

```bash
./deploy/deploy.sh setup --env dev    # once: asks questions, creates resources
./deploy/deploy.sh --env dev          # every release: build, deploy, wire
```

> [!NOTE]
> Looking to run the stack **locally**? This script is for Cloud Run only.
> See the Quick Start in the [root README](../README.md).

**Prerequisites:** `bash` (macOS, Linux, or Git Bash on Windows), `git`,
`curl`, and the [gcloud CLI](https://cloud.google.com/sdk/docs/install) with
the `beta` component if you use IAP (`gcloud components install beta`).
No local Docker is needed.

---

## What gets deployed

```mermaid
graph LR
  U["Browser"] -->|"IAP sign-in (optional)"| C["montage-client<br/>ADK web UI"]
  C -->|"ID token<br/>run.invoker"| M["montage-mcp<br/>MCP server (private)"]
  C -.->|"private IP (optional)"| S[("Cloud SQL<br/>ADK sessions")]
  M --> B[("GCS bucket")]
  U -->|"VIEW_ENDPOINT link<br/>IAP sign-in (optional)"| G["montage-sign<br/>(optional)"]
  G -->|"signed URL redirect"| B
```

| Service | Source | Access |
| --- | --- | --- |
| `montage-mcp` | [`mcp_montage/`](../mcp_montage) | Private. Only the client's service account holds `roles/run.invoker`. |
| `montage-client` | [`mcp_client/`](../mcp_client) | IAP allowlist, or public when you explicitly choose it. |
| `montage-sign` | [`sign_server/`](../sign_server) | The same IAP allowlist as the client, or public when IAP is off. Signs objects in the configured bucket only. |

Service names are defaults; each can be overridden in the environment's
config file.

---

## First-time setup

```bash
./deploy/deploy.sh setup --env dev
```

`setup` asks for each value, showing the current one as the default, then
creates what is missing and skips what already exists, so re-running it is
always safe. Answers are saved to `deploy/config/<env>.env` (gitignored).

To run setup without prompts, fill in a copy of
[`config/example.env`](./config/example.env) (or export the keys) and pass
`-y`. Setup rewrites the config file, so keep only the documented keys in it.

| Step | Asks for | Creates or verifies |
| --- | --- | --- |
| **1. Project** | `PROJECT_ID`, `REGION`, `GOOGLE_CLOUD_LOCATION` | Project (and billing link) if missing, billing check, required APIs |
| **2. Registry** | `AR_REPO` | Artifact Registry Docker repo; `cloudbuild.builds.builder` for the Compute Engine default service account, which new projects use to run builds |
| **3. Identities** | — | Service accounts `montage-mcp`, `montage-client` (and `montage-sign`) |
| **4. Bucket** | `GCS_BUCKET_NAME` | Bucket with uniform access |
| **5. Cloud SQL** *(optional)* | `SQL_INSTANCE`, `SQL_TIER`, `SQL_DATABASE`, `SQL_USER`, `VPC_NETWORK`, `VPC_SUBNET`, `VPC_SUBNET_RANGE` | VPC and subnet, private services access, private-IP Postgres, database, user, and the connection-string secret |
| **6. Sign server** *(optional)* | — | Builds and deploys `montage-sign` (behind IAP when enabled); saves `VIEW_ENDPOINT` |
| **7. Access** | `IAP_MEMBERS`, or explicit consent to a public client | IAP service agent; the allowlist is applied on every client and sign server deploy |

When run interactively, setup ends by offering to run the first deploy.

### Identities and roles

Services never run as the default compute service account, which usually
has Editor on the project.

| Service account | Roles |
| --- | --- |
| `montage-mcp` | `aiplatform.user`; `storage.objectAdmin` on the bucket |
| `montage-client` | `aiplatform.user`; `storage.objectAdmin` on the bucket; `run.invoker` on `montage-mcp`; `secretmanager.secretAccessor` on the session secret (when SQL is enabled) |
| `montage-sign` | `storage.objectViewer` on the bucket; `iam.serviceAccountTokenCreator` on itself (to sign URLs through the IAM API) |

### Cloud SQL (private IP)

Enabling Cloud SQL also creates the network it lives on:

1. a custom-mode VPC and a subnet in `REGION` for Cloud Run Direct VPC egress,
2. a `/16` private services access range (`<VPC_NETWORK>-psa`) and the
   `servicenetworking` peering,
3. a Postgres 16 (Enterprise edition) instance with `--no-assign-ip`, plus a
   database and user,
4. a generated password, stored as part of the whole connection string
   (`postgresql+asyncpg://USER:PASS@PRIVATE_IP:5432/DB`) in the Secret Manager
   secret `montage-session-uri-<env>`.

The client reads that secret with `--set-secrets SESSION_SERVICE_URI=…` and
reaches the instance with `--vpc-egress=private-ranges-only`, so calls to
montage still go out over Google's network. The password is sent to Secret
Manager on stdin and never printed or written to a config file. If the
secret already exists, setup keeps it and does not reset the password.

> [!CAUTION]
> Creating the instance takes 10–15 minutes and bills continuously. A deleted
> instance name stays reserved for about a week.

### Media links (sign server)

`mcp_montage` builds viewable links as `VIEW_ENDPOINT + <bucket>/<object>`.

| Setup choice | `VIEW_ENDPOINT` | Who can open a link |
| --- | --- | --- |
| Sign server, IAP on | `https://<montage-sign-url>/view?uri=` | `IAP_MEMBERS` only, after Google sign-in; it redirects to a short-lived signed URL |
| Sign server, IAP off | `https://<montage-sign-url>/view?uri=` | Anyone holding the link |
| Skip | unset (`https://storage.cloud.google.com/`) | Signed-in Google users with read access to the bucket |

The sign server refuses objects outside `GCS_BUCKET_NAME`, and refuses
everything when that variable is unset.

> [!NOTE]
> The signed URL it redirects to is itself a bearer link: anyone it is
> forwarded to can open the object until the URL expires
> (`SIGNED_URL_EXPIRATION_MINUTES`, 60 by default). IAP protects the
> `montage-sign` link, not the signed URL.

### Identity-Aware Proxy

A browser sends no `Authorization` header, so `--no-allow-unauthenticated`
on its own just returns 403. IAP puts a Google sign-in page in front and
admits only the allowlist. `IAP_ENABLED=1` protects both browser-facing
services, the client and the sign server, with the same members:

```bash
IAP_ENABLED="1"
IAP_MEMBERS="group:montage-users@example.com,user:someone@example.com"
```

Each member needs a type prefix: `user:`, `group:`, `domain:` or
`serviceAccount:`. A bare email is rejected before anything is deployed.

Both services are deployed with `gcloud beta run deploy --iap`, because the
flag exists only in the beta track. After each deploy of either service the
script:

1. creates the IAP service agent (`gcloud beta services identity create`),
2. grants it `roles/run.invoker` on that service,
3. grants each member `roles/iap.httpsResourceAccessor` on that service with
   `gcloud beta iap web add-iam-policy-binding --resource-type=cloud-run`.

IAP access is per service, so the allowlist is bound separately to the client
and to the sign server. A member signs in once per service hostname: opening
a media link from the client can show a brief Google sign-in redirect for the
sign server the first time.

Prefer a Google Group, so people can be added or removed without a redeploy.
The script only adds bindings. Revoke access with
`gcloud beta iap web remove-iam-policy-binding`.

If IAP is declined, setup asks for explicit consent (`CLIENT_PUBLIC=1`)
before the client is deployed with `--allow-unauthenticated`. Anyone with the
URL can then spend the project's Vertex AI quota. The sign server is also
public in that case. Setting both `IAP_ENABLED=1` and `CLIENT_PUBLIC=1` is
rejected.

> [!IMPORTANT]
> Turning IAP **off** later does not remove it from services that already
> have it: the public deploy omits `--iap` rather than passing `--no-iap`.
> Disable it once per service with
> `gcloud beta run services update <service> --no-iap --region=<region>`.

> [!WARNING]
> Direct IAP on Cloud Run requires the project to belong to an
> organization; setup checks this with `gcloud projects get-ancestors`. Its
> Google-managed OAuth client only admits users inside that organization, and
> the organization's domain-restricted sharing policy may reject outside
> members as well. External users need IAP with Identity Platform, which this
> script does not set up.

> [!CAUTION]
> Never enable IAP on `montage-mcp`. The client calls it service-to-service
> with a Google-signed ID token
> ([agent.py](../mcp_client/adk/project_montage/agent.py#L27-L40)), not an
> interactive sign-in.

---

## Everyday deploys

```bash
./deploy/deploy.sh --env dev                                  # build + deploy mcp, then client
./deploy/deploy.sh --env dev --only client                    # one service
./deploy/deploy.sh --env dev --only sign                      # update the sign server
./deploy/deploy.sh --env prod --only mcp --tag 0.6.3-ab12cd3  # redeploy / roll back, no build
./deploy/deploy.sh --env dev --dry-run                        # print commands, change nothing
```

| Flag | Values | Default |
| --- | --- | --- |
| `-e, --env` | name of a `deploy/config/<env>.env` | required |
| `--only` | `mcp` \| `client` \| `sign` | `mcp` and `client` |
| `--tag` | existing image tag; skips the build. Needs `--only` | `<version>-<git short sha>` |
| `--dry-run` | — | off |
| `-y, --yes` | skip the confirmation prompt | off |

### What a deploy does

1. **Validate and preflight** (seconds): the config exists, the client has
   exactly one access mode, `gcloud` has an active account, and the setup
   resources exist (registry, bucket, service accounts, and the session
   secret when SQL is enabled). Missing pieces are listed together with the
   `setup` command that creates them.
2. **Build on Cloud Build.** Vendored fonts are synced into
   `mcp_montage/assets/fonts` first, because `third_party/` is outside the
   build context. Images are tagged `<version>-<sha>`, with `-dirty` added
   when the service directory has uncommitted changes.
3. **Deploy `montage-mcp`** with `--no-allow-unauthenticated`, grant the
   client's service account `run.invoker`, then read the URL back with
   `gcloud run services describe`.
4. **Deploy `montage-client`** with `SERVER_URL` set to that URL, IAP or
   public access, and VPC egress plus the session secret when SQL is
   enabled. Then apply the IAP bindings.
5. **Smoke test** montage's `/version`:
   - **Without credentials** it must be refused. An HTTP 2xx fails the
     deploy with the command that removes public access.
   - **With your identity token** (`gcloud auth print-identity-token`) it
     should return 200. Anything else is a warning, because it can also mean
     your own account lacks `run.invoker`.

### Environment variables

Local `.env` files are **never** used for deploys; they point at localhost
and may hold personal API keys. They are also excluded from Cloud Build
uploads and images by each service's `.gcloudignore` and `.dockerignore`.

Each deploy renders a YAML env file per service into a temp directory:

| Service | Set by the script | Extra keys from |
| --- | --- | --- |
| mcp | `GOOGLE_GENAI_USE_VERTEXAI=True`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GCS_BUCKET_NAME`, `LOG_TO_FILE=False`, `VIEW_ENDPOINT` (when set) | `deploy/config/<env>.mcp.env` |
| client | `GOOGLE_GENAI_USE_VERTEXAI=True`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GCS_BUCKET_NAME`, `SERVER_CONNECTION_TYPE=http`, `SERVER_URL` | `deploy/config/<env>.client.env` |
| sign | `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET_NAME` | `deploy/config/<env>.sign.env` |

The extra files use dotenv syntax (`KEY=value`). Keys set by the script win
over them.

> [!WARNING]
> `--env-vars-file` **replaces** a service's entire environment. Variables
> set by hand in the Cloud Console are removed on the next deploy. Put them in
> the extra-keys file instead.

---

## Building

All images build on Cloud Build with one shared
[`cloudbuild.yaml`](./cloudbuild.yaml), using the service directory as the
build context:

```bash
gcloud builds submit mcp_montage --config=deploy/cloudbuild.yaml \
  --substitutions=_IMAGE=<registry path>,_VERSION=<tag> \
  --machine-type=e2-highcpu-8 --disk-size=200 --timeout=2400s
```

Machine type, disk and timeout are passed as flags per service, so one config
file serves all three. The montage `Dockerfile` uses BuildKit cache mounts
(`RUN --mount=type=cache`), so the config builds with `buildx` and keeps a
layer cache in the registry. Cloud Build workers are ephemeral, so that
cache is the only one that survives between builds.

---

## Tests

```bash
bash deploy/tests/run.sh          # all tests
bash deploy/tests/run.sh sql      # tests whose name contains "sql"
(cd sign_server && uv run pytest) # sign server
```

`deploy/tests/run.sh` runs the real script in a throwaway git repository
against stub `gcloud` and `curl` executables that record every call. It
asserts the commands that matter:

- montage is private and runs as its own service account,
- the client has an invoker binding, and the client and sign server get the
  right access mode and the same IAP bindings,
- secrets reach Secret Manager only over stdin,
- local `.env` values never reach a service,
- setup is idempotent,
- `--dry-run` issues no mutating command.

Extend it whenever a flag or resource changes.
