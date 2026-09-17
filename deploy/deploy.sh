#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Project Montage — Cloud Run setup and deployment.
#
#   ./deploy/deploy.sh setup --env dev     # first time: create resources
#   ./deploy/deploy.sh --env dev           # every release: build and deploy
#
# See deploy/README.md for the full guide. Runs on bash 3.2+ (macOS), Linux
# and Git Bash on Windows, so it avoids associative arrays and GNU-only flags.

set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG_DIR="$ROOT/deploy/config"

# ---------- CLI state ----------
COMMAND="deploy"
ENV_NAME=""
ONLY=""
TAG=""
DRY_RUN=0
ASSUME_YES=0
WORK_DIR=""

# Every key persisted to deploy/config/<env>.env, in file order.
CONFIG_KEYS=(
  PROJECT_ID REGION GOOGLE_CLOUD_LOCATION AR_REPO GCS_BUCKET_NAME
  MCP_SERVICE CLIENT_SERVICE SIGN_SERVICE
  SQL_ENABLED SQL_INSTANCE SQL_TIER SQL_DATABASE SQL_USER
  VPC_NETWORK VPC_SUBNET VPC_SUBNET_RANGE
  SIGN_ENABLED VIEW_ENDPOINT
  IAP_ENABLED IAP_MEMBERS CLIENT_PUBLIC
  MCP_CPU MCP_MEMORY MCP_TIMEOUT CLIENT_MEMORY CLIENT_TIMEOUT SIGN_MEMORY
)

# =========================================================================
#  Output and execution helpers
# =========================================================================

log() { printf '==> %s\n' "$*" >&2; }
info() { printf '    %s\n' "$*" >&2; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_true() {
  case "${1:-}" in
    1 | true | TRUE | True | yes | y | Y) return 0 ;;
    *) return 1 ;;
  esac
}

is_interactive() {
  [[ -t 0 ]] && ! is_true "$ASSUME_YES"
}

# run CMD... — executes a mutating command, or only prints it on --dry-run.
run() {
  printf '+ %s\n' "$*" >&2
  if is_true "$DRY_RUN"; then
    return 0
  fi
  "$@"
}

# run_quiet CMD... — like run, discarding stdout (IAM commands print policies).
run_quiet() {
  printf '+ %s\n' "$*" >&2
  if is_true "$DRY_RUN"; then
    return 0
  fi
  "$@" > /dev/null
}

# run_masked SECRET CMD... — like run, hiding SECRET in the printed command.
run_masked() {
  local secret=$1
  shift
  local shown="$*"
  printf '+ %s\n' "${shown//"$secret"/********}" >&2
  if is_true "$DRY_RUN"; then
    return 0
  fi
  "$@" > /dev/null
}

# bind CMD... — an IAM binding, retried while new service accounts propagate.
bind() {
  local attempt
  for attempt in 1 2 3; do
    if run_quiet "$@"; then
      return 0
    fi
    [[ $attempt -lt 3 ]] || break
    warn "Binding failed, retrying in ${SA_PROPAGATION_SECONDS}s (attempt $attempt/3)"
    sleep "$SA_PROPAGATION_SECONDS"
  done
  die "IAM binding failed: $*"
}

# exists GCLOUD_ARGS... — runs a read-only describe.
# Returns 0 when found, 1 when not found, and 2 for any other failure
# (disabled API, missing permission), leaving gcloud's error in EXISTS_ERROR.
EXISTS_ERROR=""
exists() {
  local output
  EXISTS_ERROR=""
  if output=$(gcloud "$@" --format="value(name)" 2>&1 > /dev/null); then
    return 0
  fi
  case "$output" in
    *NOT_FOUND* | *"not found"* | *"Not Found"* | *404* | *"does not exist"* | *"Cannot find"*)
      return 1
      ;;
  esac
  EXISTS_ERROR=$(printf '%s\n' "$output" | grep -m 1 'ERROR' || printf '%s\n' "$output" | head -n 1)
  return 2
}

# check_credentials — fail fast when gcloud cannot mint a token, instead of
# letting a later call wait on an invisible reauthentication prompt.
check_credentials() {
  local account output
  command -v gcloud > /dev/null || die "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
  account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2> /dev/null | head -n 1) || account=""
  [[ -n "$account" ]] || die "gcloud has no active account. Run: gcloud auth login"
  info "gcloud account: $account"
  if ! output=$(gcloud auth print-access-token 2>&1 > /dev/null); then
    printf '%s\n' "$output" >&2
    die "gcloud credentials for $account are not usable. Run: gcloud auth login (add --no-launch-browser over SSH)"
  fi
}

confirm() {
  local prompt=$1 reply
  if is_true "$ASSUME_YES" || is_true "$DRY_RUN"; then
    return 0
  fi
  [[ -t 0 ]] || die "Not running interactively; pass -y to confirm: $prompt"
  read -r -p "$prompt [y/N]: " reply || true
  case "$reply" in
    y | Y | yes | YES) return 0 ;;
    *) die "Aborted." ;;
  esac
}

cleanup() {
  if [[ -n "$WORK_DIR" ]]; then
    rm -rf "$WORK_DIR"
  fi
}

# =========================================================================
#  Configuration
# =========================================================================

config_file() {
  printf '%s/%s.env' "$CONFIG_DIR" "$ENV_NAME"
}

apply_defaults() {
  : "${PROJECT_ID:=}"
  : "${REGION:=us-central1}"
  : "${GOOGLE_CLOUD_LOCATION:=global}"
  : "${AR_REPO:=montage}"
  : "${GCS_BUCKET_NAME:=}"
  : "${MCP_SERVICE:=montage-mcp}"
  : "${CLIENT_SERVICE:=montage-client}"
  : "${SIGN_SERVICE:=montage-sign}"
  : "${SQL_ENABLED:=0}"
  : "${SQL_INSTANCE:=montage-sql}"
  : "${SQL_TIER:=db-f1-micro}"
  : "${SQL_DATABASE:=montage}"
  : "${SQL_USER:=montage}"
  : "${VPC_NETWORK:=montage-vpc}"
  : "${VPC_SUBNET:=montage-subnet}"
  : "${VPC_SUBNET_RANGE:=10.10.0.0/24}"
  : "${SIGN_ENABLED:=0}"
  : "${VIEW_ENDPOINT:=}"
  : "${IAP_ENABLED:=0}"
  : "${IAP_MEMBERS:=}"
  : "${CLIENT_PUBLIC:=0}"
  : "${MCP_CPU:=2}"
  : "${MCP_MEMORY:=8Gi}"
  : "${MCP_TIMEOUT:=1200}"
  : "${CLIENT_MEMORY:=2Gi}"
  : "${CLIENT_TIMEOUT:=1200}"
  : "${SIGN_MEMORY:=512Mi}"
  : "${BILLING_ACCOUNT:=}"
  : "${SA_PROPAGATION_SECONDS:=10}"
}

# Names derived from the config; recomputed after every change to it.
derive_names() {
  MCP_SA="montage-mcp@$PROJECT_ID.iam.gserviceaccount.com"
  CLIENT_SA="montage-client@$PROJECT_ID.iam.gserviceaccount.com"
  SIGN_SA="montage-sign@$PROJECT_ID.iam.gserviceaccount.com"
  REGISTRY="$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO"
  SESSION_SECRET="montage-session-uri-$ENV_NAME"
  PSA_RANGE="$VPC_NETWORK-psa"
}

require_env_name() {
  [[ -n "$ENV_NAME" ]] || die "--env is required (e.g. --env dev)"
  [[ "$ENV_NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]] ||
    die "--env must be lowercase letters, digits and hyphens: $ENV_NAME"
}

# load_config required|optional
load_config() {
  local file
  require_env_name
  file=$(config_file)
  if [[ -f "$file" ]]; then
    # shellcheck source=/dev/null
    source "$file"
  elif [[ "$1" == required ]]; then
    die "No config for env '$ENV_NAME'. Run: ./deploy/deploy.sh setup --env $ENV_NAME"
  fi
  apply_defaults
  derive_names
}

# quote VALUE — double-quoted, safe to source.
quote() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//\$/\\\$}
  value=${value//\`/\\\`}
  printf '"%s"' "$value"
}

write_config() {
  local file key
  file=$(config_file)
  if is_true "$DRY_RUN"; then
    info "(dry run) would write $file"
    return 0
  fi
  mkdir -p "$CONFIG_DIR"
  {
    printf '# Project Montage deployment config for env "%s".\n' "$ENV_NAME"
    printf '# Written by ./deploy/deploy.sh setup, which rewrites this file.\n'
    printf '# Keys are documented in deploy/config/example.env.\n'
    for key in "${CONFIG_KEYS[@]}"; do
      printf '%s=%s\n' "$key" "$(quote "${!key-}")"
    done
  } > "$file"
  info "Saved $file"
}

validate_access_mode() {
  if is_true "$IAP_ENABLED" && is_true "$CLIENT_PUBLIC"; then
    die "IAP_ENABLED and CLIENT_PUBLIC are both set. IAP cannot protect a publicly invocable service; choose one."
  fi
  if ! is_true "$IAP_ENABLED" && ! is_true "$CLIENT_PUBLIC"; then
    die "The client has no access mode. Set IAP_ENABLED=1 with IAP_MEMBERS, or CLIENT_PUBLIC=1 to allow anyone with the URL. Run: ./deploy/deploy.sh setup --env $ENV_NAME"
  fi
  if is_true "$IAP_ENABLED"; then
    validate_iap_members
  fi
}

# IAM rejects members without a type prefix, so catch them before deploying.
validate_iap_members() {
  local member members invalid=()
  [[ -n "${IAP_MEMBERS// /}" ]] ||
    die "IAP_ENABLED=1 needs IAP_MEMBERS (e.g. group:team@example.com)."
  IFS=',' read -r -a members <<< "$IAP_MEMBERS"
  for member in "${members[@]}"; do
    member=${member// /}
    [[ -n "$member" ]] || continue
    case "$member" in
      user:?* | group:?* | domain:?* | serviceAccount:?*) ;;
      *) invalid+=("$member") ;;
    esac
  done
  if [[ ${#invalid[@]} -gt 0 ]]; then
    printf 'ERROR: IAP_MEMBERS entries need a type prefix (user:, group:, domain: or serviceAccount:):\n' >&2
    for member in "${invalid[@]}"; do
      if [[ "$member" == *@* ]]; then
        printf '  - %s  (an account would be user:%s)\n' "$member" "$member" >&2
      else
        printf '  - %s  (a Workspace domain would be domain:%s)\n' "$member" "$member" >&2
      fi
    done
    die "Fix IAP_MEMBERS in $(config_file)"
  fi
}

# =========================================================================
#  Build helpers
# =========================================================================

# image_tag DIR [EXTRA_PATHS...] — <version>-<sha>[-dirty].
image_tag() {
  local dir=$1 version sha tag
  shift
  version=$(sed -n '/^version *=/{s/^version *= *"\([^"]*\)".*/\1/p;q;}' "$dir/pyproject.toml")
  [[ -n "$version" ]] || die "Could not read version from $dir/pyproject.toml"
  if ! sha=$(git -C "$ROOT" rev-parse --short HEAD 2> /dev/null); then
    printf '%s' "$version"
    return 0
  fi
  tag="$version-$sha"
  if [[ -n "$(git -C "$ROOT" status --porcelain -- "$dir" "$@" 2> /dev/null)" ]]; then
    tag="$tag-dirty"
  fi
  printf '%s' "$tag"
}

# build_image DIR IMAGE TAG [GCLOUD_FLAGS...]
build_image() {
  local dir=$1 image=$2 tag=$3
  shift 3
  log "Building $image:$tag on Cloud Build"
  run gcloud builds submit "$dir" --config=deploy/cloudbuild.yaml \
    --project="$PROJECT_ID" --substitutions="_IMAGE=$image,_VERSION=$tag" "$@"
}

# render_env_file OUTPUT EXTRA_FILE KEY=VALUE... — YAML for --env-vars-file.
# Keys from EXTRA_FILE (dotenv, optional) come first; KEY=VALUE pairs win.
render_env_file() {
  local output=$1 extra=$2
  shift 2
  {
    if [[ -f "$extra" ]]; then
      cat "$extra"
      printf '\n'
    fi
    printf '%s\n' "$@"
  } | awk '
    {
      line = $0
      sub(/\r$/, "", line)
      if (line ~ /^[[:space:]]*(#|$)/) next
      sub(/^[[:space:]]*export[[:space:]]+/, "", line)
      eq = index(line, "=")
      if (eq == 0) next
      key = substr(line, 1, eq - 1)
      gsub(/[[:space:]]/, "", key)
      value = substr(line, eq + 1)
      if (value ~ /^".*"$/ || value ~ /^\047.*\047$/) {
        value = substr(value, 2, length(value) - 2)
      }
      if (!(key in seen)) {
        seen[key] = 1
        order[++count] = key
      }
      values[key] = value
    }
    END {
      for (i = 1; i <= count; i++) {
        value = values[order[i]]
        escaped = ""
        for (j = 1; j <= length(value); j++) {
          c = substr(value, j, 1)
          if (c == "\\" || c == "\"") escaped = escaped "\\"
          escaped = escaped c
        }
        printf "%s: \"%s\"\n", order[i], escaped
      }
    }' > "$output"
}

# service_url SERVICE — the deployed URL, or a placeholder on --dry-run.
service_url() {
  local service=$1 url=""
  url=$(gcloud run services describe "$service" --region="$REGION" \
    --project="$PROJECT_ID" --format="value(status.url)" 2> /dev/null) || url=""
  if [[ -z "$url" ]]; then
    if is_true "$DRY_RUN"; then
      printf 'https://%s.example.invalid' "$service"
      return 0
    fi
    return 1
  fi
  printf '%s' "$url"
}

project_number() {
  local number
  number=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2> /dev/null) || number=""
  if [[ -z "$number" ]]; then
    is_true "$DRY_RUN" || die "Could not read the project number of $PROJECT_ID"
    number="PROJECT_NUMBER"
  fi
  printf '%s' "$number"
}

# =========================================================================
#  Deploy
# =========================================================================

wants() {
  local service=$1
  if [[ -z "$ONLY" ]]; then
    [[ "$service" == mcp || "$service" == client ]]
  else
    [[ "$service" == "$ONLY" ]]
  fi
}

# check_resource LABEL GCLOUD_ARGS... — appends to preflight's problems.
check_resource() {
  local label=$1 status=0
  shift
  exists "$@" || status=$?
  case "$status" in
    0) ;;
    1) problems+=("$label") ;;
    *) problems+=("$label — could not check: $EXISTS_ERROR") ;;
  esac
}

preflight() {
  local problems=()

  check_credentials

  check_resource "Artifact Registry repository $AR_REPO in $REGION" \
    artifacts repositories describe "$AR_REPO" --location="$REGION" --project="$PROJECT_ID"
  check_resource "bucket gs://$GCS_BUCKET_NAME" \
    storage buckets describe "gs://$GCS_BUCKET_NAME" --project="$PROJECT_ID"

  local sa
  local accounts=()
  if wants mcp || wants client; then accounts+=("$MCP_SA" "$CLIENT_SA"); fi
  if wants sign; then accounts+=("$SIGN_SA"); fi
  for sa in "${accounts[@]}"; do
    check_resource "service account $sa" \
      iam service-accounts describe "$sa" --project="$PROJECT_ID"
  done

  if wants client && is_true "$SQL_ENABLED"; then
    check_resource "Secret Manager secret $SESSION_SECRET" \
      secrets describe "$SESSION_SECRET" --project="$PROJECT_ID"
  fi

  if [[ ${#problems[@]} -gt 0 ]]; then
    printf 'ERROR: Missing setup resources in project %s:\n' "$PROJECT_ID" >&2
    printf '  - %s\n' "${problems[@]}" >&2
    die "Run: ./deploy/deploy.sh setup --env $ENV_NAME"
  fi
}

deploy_mcp() {
  local image="$REGISTRY/$MCP_SERVICE" tag env_file
  tag=${TAG:-$(image_tag mcp_montage third_party/fonts)}

  if [[ -z "$TAG" ]]; then
    log "Syncing vendored fonts into mcp_montage/assets"
    (cd mcp_montage && run_quiet bash sync_fonts_from_third_party.sh)
    build_image mcp_montage "$image" "$tag" \
      --machine-type=e2-highcpu-8 --disk-size=200 --timeout=2400s
  fi

  env_file="$WORK_DIR/mcp.yaml"
  local pairs=(
    "GOOGLE_GENAI_USE_VERTEXAI=True"
    "GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
    "GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION"
    "GCS_BUCKET_NAME=$GCS_BUCKET_NAME"
    "LOG_TO_FILE=False"
  )
  if [[ -n "$VIEW_ENDPOINT" ]]; then
    pairs+=("VIEW_ENDPOINT=$VIEW_ENDPOINT")
  fi
  render_env_file "$env_file" "$CONFIG_DIR/$ENV_NAME.mcp.env" "${pairs[@]}"

  log "Deploying $MCP_SERVICE (private)"
  run gcloud run deploy "$MCP_SERVICE" --image="$image:$tag" \
    --region="$REGION" --project="$PROJECT_ID" \
    --service-account="$MCP_SA" --no-allow-unauthenticated \
    --env-vars-file "$env_file" --port=8080 \
    --cpu="$MCP_CPU" --memory="$MCP_MEMORY" --timeout="$MCP_TIMEOUT" \
    --session-affinity --no-cpu-throttling

  bind gcloud run services add-iam-policy-binding "$MCP_SERVICE" \
    --region="$REGION" --project="$PROJECT_ID" \
    --member="serviceAccount:$CLIENT_SA" --role=roles/run.invoker
}

deploy_client() {
  local mcp_url=$1 image="$REGISTRY/$CLIENT_SERVICE" tag env_file
  tag=${TAG:-$(image_tag mcp_client)}

  if [[ -z "$TAG" ]]; then
    build_image mcp_client "$image" "$tag" \
      --machine-type=e2-highcpu-8 --disk-size=100 --timeout=1800s
  fi

  env_file="$WORK_DIR/client.yaml"
  render_env_file "$env_file" "$CONFIG_DIR/$ENV_NAME.client.env" \
    "GOOGLE_GENAI_USE_VERTEXAI=True" \
    "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    "GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION" \
    "GCS_BUCKET_NAME=$GCS_BUCKET_NAME" \
    "SERVER_CONNECTION_TYPE=http" \
    "SERVER_URL=$mcp_url"

  local network=()
  if is_true "$SQL_ENABLED"; then
    network=(
      --network="$VPC_NETWORK" --subnet="$VPC_SUBNET" --vpc-egress=private-ranges-only
      --set-secrets="SESSION_SERVICE_URI=$SESSION_SECRET:latest"
    )
  fi

  deploy_with_access "$CLIENT_SERVICE" --image="$image:$tag" \
    --region="$REGION" --project="$PROJECT_ID" \
    --service-account="$CLIENT_SA" \
    --env-vars-file "$env_file" --port=8080 \
    --memory="$CLIENT_MEMORY" --timeout="$CLIENT_TIMEOUT" \
    ${network[@]+"${network[@]}"}
}

# deploy_with_access SERVICE DEPLOY_FLAGS... — deploys a browser-facing
# service behind IAP (admitting IAP_MEMBERS) when IAP_ENABLED, else publicly.
deploy_with_access() {
  local service=$1
  shift
  if is_true "$IAP_ENABLED"; then
    log "Deploying $service (IAP)"
    # --iap is only available in the beta track of gcloud run deploy.
    run gcloud beta run deploy "$service" "$@" --iap --no-allow-unauthenticated
    apply_iap_bindings "$service"
  else
    log "Deploying $service (public)"
    run gcloud run deploy "$service" "$@" --allow-unauthenticated
  fi
}

# apply_iap_bindings SERVICE
apply_iap_bindings() {
  local service=$1 number member members
  log "Applying IAP access for $service"
  number=$(project_number)
  run_quiet gcloud beta services identity create --service=iap.googleapis.com --project="$PROJECT_ID"
  bind gcloud run services add-iam-policy-binding "$service" \
    --region="$REGION" --project="$PROJECT_ID" \
    --member="serviceAccount:service-$number@gcp-sa-iap.iam.gserviceaccount.com" \
    --role=roles/run.invoker

  IFS=',' read -r -a members <<< "$IAP_MEMBERS"
  for member in "${members[@]}"; do
    member=${member// /}
    [[ -n "$member" ]] || continue
    bind gcloud beta iap web add-iam-policy-binding --resource-type=cloud-run \
      --service="$service" --region="$REGION" --project="$PROJECT_ID" \
      --member="$member" --role=roles/iap.httpsResourceAccessor --condition=None
  done
}

deploy_sign() {
  local image="$REGISTRY/$SIGN_SERVICE" tag env_file
  tag=${TAG:-$(image_tag sign_server)}

  if [[ -z "$TAG" ]]; then
    build_image sign_server "$image" "$tag"
  fi

  env_file="$WORK_DIR/sign.yaml"
  render_env_file "$env_file" "$CONFIG_DIR/$ENV_NAME.sign.env" \
    "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    "GCS_BUCKET_NAME=$GCS_BUCKET_NAME"

  deploy_with_access "$SIGN_SERVICE" --image="$image:$tag" \
    --region="$REGION" --project="$PROJECT_ID" \
    --service-account="$SIGN_SA" \
    --env-vars-file "$env_file" --port=8080 --memory="$SIGN_MEMORY"
}

# smoke_test MCP_URL — montage must reject anonymous calls and be reachable.
smoke_test() {
  local url="$1/version" code token
  log "Smoke test: $url"

  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "$url" 2> /dev/null) || true
  if [[ "$code" == 2* ]]; then
    die "$MCP_SERVICE answered HTTP $code without credentials: it is public. Remove access with: gcloud run services remove-iam-policy-binding $MCP_SERVICE --region=$REGION --project=$PROJECT_ID --member=allUsers --role=roles/run.invoker"
  fi
  info "Without credentials: HTTP $code (expected 401/403)"

  token=$(gcloud auth print-identity-token 2> /dev/null) || token=""
  if [[ -z "$token" ]]; then
    warn "Could not get an identity token to verify $MCP_SERVICE is reachable."
    return 0
  fi
  # A cold start loads the ~1.2 GB alignment model, so allow a long wait.
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 300 \
    -H "Authorization: Bearer $token" "$url" 2> /dev/null) || true
  if [[ "$code" == 200 ]]; then
    info "With your identity: HTTP 200"
  else
    warn "$MCP_SERVICE returned HTTP $code for your identity; check the revision logs (or your own run.invoker access)."
  fi
}

cmd_deploy() {
  load_config required
  case "$ONLY" in
    "" | mcp | client | sign) ;;
    *) die "--only must be one of: mcp, client, sign" ;;
  esac
  [[ -z "$TAG" || -n "$ONLY" ]] ||
    die "--tag needs --only, because each service has its own image version"
  if wants client; then
    validate_access_mode
  fi
  if wants sign && ! is_true "$SIGN_ENABLED"; then
    die "SIGN_ENABLED is not set for env '$ENV_NAME'. Enable it with: ./deploy/deploy.sh setup --env $ENV_NAME"
  fi
  if wants sign && is_true "$IAP_ENABLED"; then
    validate_iap_members
  fi
  [[ -n "$PROJECT_ID" && -n "$GCS_BUCKET_NAME" ]] ||
    die "PROJECT_ID and GCS_BUCKET_NAME must be set in $(config_file)"

  log "Preflight for env '$ENV_NAME' (project $PROJECT_ID)"
  preflight

  confirm "Deploy ${ONLY:-mcp + client} to project $PROJECT_ID?"
  WORK_DIR=$(mktemp -d)

  if wants sign; then
    deploy_sign
  fi

  local mcp_url=""
  if wants mcp; then
    deploy_mcp
  fi
  if wants mcp || wants client; then
    mcp_url=$(service_url "$MCP_SERVICE") ||
      die "$MCP_SERVICE is not deployed in $REGION. Deploy it first: ./deploy/deploy.sh --env $ENV_NAME --only mcp"
  fi
  if wants client; then
    deploy_client "$mcp_url"
  fi

  if is_true "$DRY_RUN"; then
    log "Dry run complete; nothing was changed."
    return 0
  fi
  if [[ -n "$mcp_url" ]]; then
    smoke_test "$mcp_url"
  fi

  log "Deployment complete"
  if [[ -n "$mcp_url" ]]; then info "mcp:    $mcp_url"; fi
  if wants client; then info "client: $(service_url "$CLIENT_SERVICE" || echo '?')"; fi
  if wants sign; then info "sign:   $(service_url "$SIGN_SERVICE" || echo '?')"; fi
}

# =========================================================================
#  Setup
# =========================================================================

# ask VAR PROMPT — prompt with the current value as default when interactive.
ask() {
  local var=$1 prompt=$2 current reply
  current=${!var-}
  if is_interactive; then
    read -r -p "$prompt [$current]: " reply || true
    if [[ -n "$reply" ]]; then
      current=$reply
    fi
  fi
  printf -v "$var" '%s' "$current"
}

# ask_bool VAR PROMPT — stores 1 or 0.
ask_bool() {
  local var=$1 prompt=$2 current reply
  current=$(is_true "${!var-}" && echo 1 || echo 0)
  if is_interactive; then
    read -r -p "$prompt [$(is_true "$current" && echo Y/n || echo y/N)]: " reply || true
    case "$reply" in
      y | Y | yes | YES) current=1 ;;
      n | N | no | NO) current=0 ;;
    esac
  fi
  printf -v "$var" '%s' "$current"
}

require() {
  local var=$1 hint=$2
  [[ -n "${!var-}" ]] || die "$var is required ($hint). Set it in $(config_file) or the environment, or run setup interactively."
}

collect_answers() {
  if [[ -z "$PROJECT_ID" ]] && is_interactive; then
    PROJECT_ID=$(gcloud config get-value project 2> /dev/null || true)
  fi

  log "Project"
  ask PROJECT_ID "Google Cloud project ID"
  require PROJECT_ID "Google Cloud project ID"
  ask REGION "Region for Cloud Run, registry, bucket and SQL"
  ask GOOGLE_CLOUD_LOCATION "Vertex AI location for Gemini/Veo calls"
  ask AR_REPO "Artifact Registry repository"
  : "${GCS_BUCKET_NAME:=$PROJECT_ID-montage}"
  ask GCS_BUCKET_NAME "GCS bucket for generated media (created if missing)"

  log "Cloud SQL — persistent ADK sessions on a private IP (optional, ~10-15 min, billed continuously)"
  ask_bool SQL_ENABLED "Set up Cloud SQL?"
  if is_true "$SQL_ENABLED"; then
    ask SQL_INSTANCE "Instance name"
    ask SQL_TIER "Machine tier"
    ask SQL_DATABASE "Database name"
    ask SQL_USER "Database user"
    ask VPC_NETWORK "VPC network (created if missing)"
    ask VPC_SUBNET "Subnet for Cloud Run egress (created if missing)"
    ask VPC_SUBNET_RANGE "Subnet IP range"
  fi

  log "Sign server — short-lived signed links to private media (optional)"
  ask_bool SIGN_ENABLED "Deploy the sign server?"

  log "Web access"
  ask_bool IAP_ENABLED "Protect the web client with Google sign-in (IAP)? Requires an organization"
  if is_true "$IAP_ENABLED"; then
    CLIENT_PUBLIC=0
    ask IAP_MEMBERS "Allowed members, comma-separated (user:a@x.com, group:g@x.com, domain:x.com)"
    require IAP_MEMBERS "e.g. group:team@example.com"
    validate_iap_members
  else
    info "Without IAP, anyone with the URL can use the app and spend Vertex AI quota."
    ask_bool CLIENT_PUBLIC "Deploy the web client publicly?"
    is_true "$CLIENT_PUBLIC" ||
      die "The web client needs IAP or public access. Re-run setup and choose one."
  fi

  derive_names
}

required_apis() {
  local apis=(
    run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
    aiplatform.googleapis.com iam.googleapis.com storage.googleapis.com
    compute.googleapis.com
  )
  if is_true "$SQL_ENABLED"; then
    apis+=(sqladmin.googleapis.com servicenetworking.googleapis.com secretmanager.googleapis.com)
  fi
  if is_true "$SIGN_ENABLED"; then
    apis+=(iamcredentials.googleapis.com)
  fi
  if is_true "$IAP_ENABLED"; then
    apis+=(iap.googleapis.com)
  fi
  printf '%s\n' "${apis[@]}"
}

setup_project() {
  log "Project $PROJECT_ID"
  if exists projects describe "$PROJECT_ID"; then
    local billing
    billing=$(gcloud billing projects describe "$PROJECT_ID" --format="value(billingEnabled)" 2> /dev/null) || billing=""
    [[ "$billing" == True ]] || warn "Could not confirm billing is enabled for $PROJECT_ID."
  else
    ask BILLING_ACCOUNT "Project does not exist. Billing account ID to link (gcloud billing accounts list)"
    if is_true "$DRY_RUN"; then
      : "${BILLING_ACCOUNT:=BILLING_ACCOUNT_ID}"
    fi
    require BILLING_ACCOUNT "needed to create the project"
    run gcloud projects create "$PROJECT_ID"
    run gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
  fi

  if is_true "$IAP_ENABLED"; then
    gcloud projects get-ancestors "$PROJECT_ID" --format="value(type)" 2> /dev/null | grep -qx organization ||
      die "IAP on Cloud Run requires the project to belong to an organization, and $PROJECT_ID does not. Re-run setup without IAP."
  fi

  local apis
  apis=$(required_apis | tr '\n' ' ')
  # shellcheck disable=SC2086 # word splitting of the API list is intended
  run gcloud services enable $apis --project="$PROJECT_ID"
}

setup_registry() {
  log "Artifact Registry"
  if exists artifacts repositories describe "$AR_REPO" --location="$REGION" --project="$PROJECT_ID"; then
    info "Repository $AR_REPO exists"
  else
    run gcloud artifacts repositories create "$AR_REPO" --repository-format=docker \
      --location="$REGION" --project="$PROJECT_ID"
  fi

  # New projects run Cloud Build as the Compute Engine default service
  # account, which may lack permission to push images and write logs.
  local number
  number=$(project_number)
  bind gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$number-compute@developer.gserviceaccount.com" \
    --role=roles/cloudbuild.builds.builder --condition=None
}

ensure_service_account() {
  local name=$1 display=$2 email="$1@$PROJECT_ID.iam.gserviceaccount.com"
  if exists iam service-accounts describe "$email" --project="$PROJECT_ID"; then
    info "Service account $email exists"
  else
    run gcloud iam service-accounts create "$name" --display-name="$display" --project="$PROJECT_ID"
    if ! is_true "$DRY_RUN"; then
      sleep "$SA_PROPAGATION_SECONDS"
    fi
  fi
}

setup_identities() {
  log "Service accounts"
  ensure_service_account montage-mcp "Project Montage MCP server"
  ensure_service_account montage-client "Project Montage web client"
  if is_true "$SIGN_ENABLED"; then
    ensure_service_account montage-sign "Project Montage sign server"
  fi

  local sa
  for sa in "$MCP_SA" "$CLIENT_SA"; do
    bind gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$sa" --role=roles/aiplatform.user --condition=None
  done
}

setup_bucket() {
  log "Bucket gs://$GCS_BUCKET_NAME"
  if exists storage buckets describe "gs://$GCS_BUCKET_NAME" --project="$PROJECT_ID"; then
    info "Bucket exists"
  else
    run gcloud storage buckets create "gs://$GCS_BUCKET_NAME" --project="$PROJECT_ID" \
      --location="$REGION" --uniform-bucket-level-access
  fi

  local sa
  for sa in "$MCP_SA" "$CLIENT_SA"; do
    bind gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET_NAME" \
      --member="serviceAccount:$sa" --role=roles/storage.objectAdmin
  done
}

setup_network() {
  log "VPC $VPC_NETWORK (private IP for Cloud SQL)"
  if ! exists compute networks describe "$VPC_NETWORK" --project="$PROJECT_ID"; then
    run gcloud compute networks create "$VPC_NETWORK" --subnet-mode=custom --project="$PROJECT_ID"
  fi
  if ! exists compute networks subnets describe "$VPC_SUBNET" --region="$REGION" --project="$PROJECT_ID"; then
    run gcloud compute networks subnets create "$VPC_SUBNET" --network="$VPC_NETWORK" \
      --region="$REGION" --range="$VPC_SUBNET_RANGE" --project="$PROJECT_ID"
  fi
  if ! exists compute addresses describe "$PSA_RANGE" --global --project="$PROJECT_ID"; then
    run gcloud compute addresses create "$PSA_RANGE" --global --purpose=VPC_PEERING \
      --prefix-length=16 --network="$VPC_NETWORK" --project="$PROJECT_ID"
  fi
  local peerings
  peerings=$(gcloud services vpc-peerings list --network="$VPC_NETWORK" \
    --project="$PROJECT_ID" --format="value(peering)" 2> /dev/null) || peerings=""
  if [[ -z "$peerings" ]]; then
    run gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com \
      --ranges="$PSA_RANGE" --network="$VPC_NETWORK" --project="$PROJECT_ID"
  else
    info "Private services access is connected"
  fi
}

generate_password() {
  head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | cut -c 1-32
}

setup_sql() {
  log "Cloud SQL $SQL_INSTANCE"
  if exists sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID"; then
    info "Instance exists"
  else
    info "Creating the instance takes 10-15 minutes."
    run gcloud sql instances create "$SQL_INSTANCE" --database-version=POSTGRES_16 \
      --edition=enterprise --tier="$SQL_TIER" --region="$REGION" \
      --network="projects/$PROJECT_ID/global/networks/$VPC_NETWORK" --no-assign-ip \
      --project="$PROJECT_ID"
  fi
  if ! exists sql databases describe "$SQL_DATABASE" --instance="$SQL_INSTANCE" --project="$PROJECT_ID"; then
    run gcloud sql databases create "$SQL_DATABASE" --instance="$SQL_INSTANCE" --project="$PROJECT_ID"
  fi

  if exists secrets describe "$SESSION_SECRET" --project="$PROJECT_ID"; then
    info "Secret $SESSION_SECRET exists; keeping the current database password"
  else
    local password ip users uri
    password=$(generate_password)
    users=$(gcloud sql users list --instance="$SQL_INSTANCE" --project="$PROJECT_ID" \
      --format="value(name)" 2> /dev/null) || users=""
    if printf '%s\n' "$users" | grep -qx "$SQL_USER"; then
      run_masked "$password" gcloud sql users set-password "$SQL_USER" \
        --instance="$SQL_INSTANCE" --password="$password" --project="$PROJECT_ID"
    else
      run_masked "$password" gcloud sql users create "$SQL_USER" \
        --instance="$SQL_INSTANCE" --password="$password" --project="$PROJECT_ID"
    fi
    ip=$(gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID" \
      --format="value(ipAddresses[0].ipAddress)" 2> /dev/null) || ip=""
    if [[ -z "$ip" ]]; then
      is_true "$DRY_RUN" || die "Could not read the private IP of $SQL_INSTANCE"
      ip="PRIVATE_IP"
    fi
    uri="postgresql+asyncpg://$SQL_USER:$password@$ip:5432/$SQL_DATABASE"
    printf '%s' "$uri" | run gcloud secrets create "$SESSION_SECRET" --data-file=- \
      --replication-policy=automatic --project="$PROJECT_ID"
  fi

  bind gcloud secrets add-iam-policy-binding "$SESSION_SECRET" \
    --member="serviceAccount:$CLIENT_SA" --role=roles/secretmanager.secretAccessor \
    --project="$PROJECT_ID"
}

setup_sign() {
  log "Sign server $SIGN_SERVICE"
  # Signing through the IAM API needs token-creator rights on itself.
  bind gcloud iam service-accounts add-iam-policy-binding "$SIGN_SA" \
    --member="serviceAccount:$SIGN_SA" --role=roles/iam.serviceAccountTokenCreator \
    --project="$PROJECT_ID"
  bind gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET_NAME" \
    --member="serviceAccount:$SIGN_SA" --role=roles/storage.objectViewer

  if [[ -n "$VIEW_ENDPOINT" ]] &&
    exists run services describe "$SIGN_SERVICE" --region="$REGION" --project="$PROJECT_ID"; then
    info "Sign server is deployed; update it with: ./deploy/deploy.sh --env $ENV_NAME --only sign"
    return 0
  fi

  WORK_DIR=${WORK_DIR:-$(mktemp -d)}
  deploy_sign
  local url
  url=$(service_url "$SIGN_SERVICE") || die "Could not read the URL of $SIGN_SERVICE"
  VIEW_ENDPOINT="$url/view?uri="
}

setup_iap() {
  log "Identity-Aware Proxy"
  run_quiet gcloud beta services identity create --service=iap.googleapis.com --project="$PROJECT_ID"
  info "Access for $IAP_MEMBERS is applied on every client and sign server deploy."
}

cmd_setup() {
  load_config optional

  command -v gcloud > /dev/null || die "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
  local account
  account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2> /dev/null | head -n 1) || account=""
  if [[ -z "$account" ]] && is_interactive; then
    # The one gcloud command that must be allowed to interact.
    CLOUDSDK_CORE_DISABLE_PROMPTS=0 run gcloud auth login
  fi
  check_credentials

  collect_answers
  write_config
  confirm "Create or verify these resources in project $PROJECT_ID?"

  setup_project
  setup_registry
  setup_identities
  setup_bucket
  if is_true "$SQL_ENABLED"; then
    setup_network
    setup_sql
  fi
  if is_true "$SIGN_ENABLED"; then
    setup_sign
    write_config
  fi
  if is_true "$IAP_ENABLED"; then
    setup_iap
  fi

  log "Setup complete for env '$ENV_NAME'"
  info "Deploy with: ./deploy/deploy.sh --env $ENV_NAME"
  if is_interactive && ! is_true "$DRY_RUN"; then
    local deploy_now=1
    ask_bool deploy_now "Run the first deploy now?"
    if is_true "$deploy_now"; then
      ASSUME_YES=1
      cmd_deploy
    fi
  fi
}

# =========================================================================
#  Entry point
# =========================================================================

usage() {
  cat << 'EOF'
Usage:
  ./deploy/deploy.sh setup --env NAME [--dry-run] [-y]
  ./deploy/deploy.sh [deploy] --env NAME [--only mcp|client|sign] [--tag TAG] [--dry-run] [-y]

Commands:
  setup    Ask for settings, then create or verify every cloud resource.
           Safe to re-run. Saves answers to deploy/config/NAME.env.
  deploy   Build on Cloud Build and deploy mcp, then client (default).

Options:
  -e, --env NAME    Environment config to use (required).
  --only SERVICE    Deploy one service: mcp, client or sign.
  --tag TAG         Deploy an existing image tag without building (needs --only).
  --dry-run         Print the commands that change resources; run none of them.
  -y, --yes         Do not prompt; use config values and skip confirmation.
  -h, --help        Show this help.
EOF
}

parse_args() {
  if [[ $# -gt 0 && "$1" != -* ]]; then
    COMMAND=$1
    shift
  fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -e | --env) ENV_NAME=${2-} && shift ;;
      --env=*) ENV_NAME=${1#*=} ;;
      --only) ONLY=${2-} && shift ;;
      --only=*) ONLY=${1#*=} ;;
      --tag) TAG=${2-} && shift ;;
      --tag=*) TAG=${1#*=} ;;
      --dry-run) DRY_RUN=1 ;;
      -y | --yes) ASSUME_YES=1 ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        usage >&2
        die "Unknown argument: $1"
        ;;
    esac
    shift
  done
}

main() {
  parse_args "$@"
  # Output of most gcloud checks is hidden, so a gcloud question (enable an
  # API? reauthenticate?) would be invisible and hang the terminal. With
  # prompts disabled gcloud fails with an error instead.
  export CLOUDSDK_CORE_DISABLE_PROMPTS=1
  cd "$ROOT"
  trap cleanup EXIT
  case "$COMMAND" in
    setup)
      [[ -z "$ONLY" && -z "$TAG" ]] || die "--only and --tag apply to deploy, not setup"
      cmd_setup
      ;;
    deploy) cmd_deploy ;;
    help) usage ;;
    *)
      usage >&2
      die "Unknown command: $COMMAND"
      ;;
  esac
}

main "$@"
