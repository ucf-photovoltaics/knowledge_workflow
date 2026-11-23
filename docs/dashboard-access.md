# Dashboard access on Cloud Run

## Current setup: application-managed passwords and a private bucket file

Login, sessions, roles and revocation are enforced by the Shiny application's
server-side access gate. Google sign-in and Secret Manager are not required.
The current deployment uses the existing private `research-dpv-kw-outputs` bucket
for persistent configuration at `private/access.json`. The bucket uses uniform
bucket-level access; public bucket/project bindings were checked before upload.

The runtime mounts only its `private` prefix at `/mnt/dpv-access`, read-only,
with metadata caches disabled (`stat-cache-ttl=0;type-cache-ttl=0`). Set
`DPV_ACCESS_CONFIG=/mnt/dpv-access/access.json`. This separate mount keeps
credential refresh independent of caching on the research-output mount. The
application rereads the file every 30 seconds; idle WebSocket sessions are checked
every 5 seconds. The existing `/app/outputs` mount remains the share root.

Update credentials locally using the existing helper or a private editor, then
upload the complete validated file to rotate/revoke credentials without a rebuild:

```powershell
gcloud storage cp outputs/dashboard/private/access.json gs://research-dpv-kw-outputs/private/access.json --cache-control=private,no-store
```

The application blocks `private/` in artifact browsing, media and shared-file
routes. Do not make this bucket public. Users with direct bucket read permission
can read this configuration; file-viewer restrictions apply to app visitors, not
to Google Cloud IAM principals. Passwords remain salted hashes and the signing
key stays server-side. The private file is excluded from source uploads/images.
This choice uses the runtime's existing bucket access and needs no new secret IAM
grant. The later Secret Manager sections describe the original optional approach;
they are not required for this deployment.

The dashboard requires a login before any Shiny content, documentation, downloads,
media or WebSocket connection is accessible. No passwords or signing keys are
included in source. `dpv_dashboard/access.example.json` is intentionally invalid
until you supply your private signing key and password hashes.

## Access tiers

| Role | Access | Credential policy |
| --- | --- | --- |
| `team` | Existing Shiny dashboard, subject to its deployment's viewer/editor setting | One long-lived DPV team password |
| `collaborator` | Read-only file viewer for explicitly granted project releases | Separate ID/password per person or group; independently revocable |
| `paper` | Read-only file viewer for explicitly granted publication releases | Stable ID/password suitable for publishing in the paper |

The restricted file viewer lists approved files, provides escaped text previews,
and downloads originals as attachments. It deliberately has no Shiny session,
job controls, credential editor, global output discovery, media-token access or
research chat. Collaborators do not get the interactive Shiny graph/exploration
pages. Every request uses the current credential's share list.

The working Cloud Run image still defaults to `DPV_VIEWER=1`: team login does not
enable workflow execution. Enabling editor mode (`DPV_VIEWER=0`) is a separate
deployment choice requiring the existing pipeline prerequisites and durable
workspace configuration. This change does not restart or alter running jobs.

## Prepare private configuration

1. Copy `dpv_dashboard/access.example.json` to
   `outputs/dashboard/private/access.json` (ignored by Git and Cloud build upload).
2. Supply a private, random session signing key of at least 32 bytes from your
   password manager. All instances of one service must use the same key.
3. Run the helper below separately for the team and each collaborator/publication
   password. It prompts without echoing, checks confirmation, and prints only a
   salted PBKDF2-SHA256 hash. Paste the result into `password_hash` locally.
4. Set `shares` to the exact approved releases and paths. Remove unused example
   credentials/shares. Access IDs are public identifiers, not secret usernames.

```powershell
outputs/dashboard/.venv/Scripts/python.exe scripts/dashboard-access.py
```

Passwords must be 12–1024 characters. The helper uses 600,000 PBKDF2 iterations.
Never put plaintext passwords in command arguments, URLs, source control or logs.
Share each access ID and its password separately through your preferred channel.

`DPV_SHARE_ROOT` is a directory on the server (normally a read-only mounted bucket).
Share `root` values are relative to it. `files` contains exact relative POSIX paths;
wildcards and user-supplied filesystem paths are not accepted. Traversal, absolute
paths, hidden/private paths and credential-file extensions are rejected. Symlinks
resolving outside a release are not served. Do not include confidential content
inside an approved file; the app cannot infer its sensitivity.

To expose a dedicated publication bucket in its entirety, mount only that bucket
as `DPV_SHARE_ROOT`, set the publication share's `root` to `.` and
`whole_root` to `true`. At most 10,000 files are supported. The default is an
explicit file list. Whole-root mode exposes new eligible files placed in that
root too; use an immutable release bucket or explicit lists for reproducibility.

## Rotation and revocation

Upload a new **version of the mounted Secret Manager secret**, rather than changing
container environment variables. Keep the session signing key unchanged unless
you want everyone signed out.

- Revoke a collaborator: set their `enabled` to `false`, or remove their entry.
- Rotate their password: replace only their `password_hash` and increment their
  `version` string.
- Force sign-in again without changing a password: increment that credential's
  `version`.
- Change approved projects: edit that credential's `shares` list.
- Change files within a share: edit the share's file list; the next authorized
  request uses the refreshed list.

Other credentials remain valid. A configuration file is reread every 30 seconds
per instance; active team WebSockets are rechecked at most every 5 seconds.
Revocation therefore takes effect within approximately 35 seconds under normal
operation, with a 60-second operational allowance for processing/scheduling.
Missing, oversized or malformed refreshed configuration denies access with 503;
the last valid config is not retained indefinitely. Mount the `latest` version.

Cookies are signed, HTTP-only, Secure and SameSite=Strict; sessions last 8 hours
by default (set `DPV_ACCESS_SESSION_SECONDS`, 60–86400). They work across instances
using the shared key. Browser logout removes that browser's cookie; credential
revocation/version changes are the mechanism to invalidate copies globally.
Login forms require a signed cookie-backed challenge. Password hashing runs off
the event loop with bounded concurrency, and login attempts are limited to 10
per access ID per minute **per instance**. This is not a distributed quota; use
your load balancer/Cloud Armor for centralized abuse controls if needed.

Existing server-side jobs are not cancelled by logout or credential revocation;
the credential loses access to their controls and results. A download already
authorized can finish. Revocation cannot recall files someone already downloaded.

## Working dashboard deployment

Use a service account with Secret Manager Secret Accessor on the dashboard's
access secret. Keep any existing workspace/storage permissions separate. The
following commands are templates; substitute your project, region, service,
service account, bucket and secret names. They have not been executed for you.

```powershell
# First version (create once):
gcloud secrets create dpv-dashboard-access --replication-policy=user-managed --locations=REGION --data-file=outputs/dashboard/private/access.json --project=PROJECT_ID
gcloud secrets add-iam-policy-binding dpv-dashboard-access --member=serviceAccount:DASHBOARD_SA --role=roles/secretmanager.secretAccessor --project=PROJECT_ID

gcloud run deploy DASHBOARD_SERVICE --source . --project PROJECT_ID --region REGION --service-account DASHBOARD_SA --allow-unauthenticated --update-env-vars DPV_ACCESS_CONFIG=/secrets/dpv/access.json,DPV_SHARE_ROOT=/mnt/shared --update-secrets /secrets/dpv/access.json=dpv-dashboard-access:latest

# Mount the chosen share bucket read-only (service account needs bucket-level Object Viewer):
gcloud run services update DASHBOARD_SERVICE --project PROJECT_ID --region REGION --add-volume mount-path=/mnt/shared,type=cloud-storage,bucket=SHARE_BUCKET,readonly=true

# Subsequent rotation/revocation; no image rebuild:
gcloud secrets versions add dpv-dashboard-access --data-file=outputs/dashboard/private/access.json --project=PROJECT_ID
```

Cloud Run's unauthenticated IAM setting lets browsers reach the app's login
screen. The app enforces the password check; Cloud Run IAM access is separate.
Do not also expose an older, unprotected revision/service or a public working
bucket that bypasses this gate. Retire old unprotected revision URLs when moving
traffic. Prefer 100% traffic to the protected revision.

Cloud Run terminates HTTPS; Secure cookies must stay enabled there. Shiny uses
stateful WebSockets, so keep the service's existing session affinity and timeout
configuration. Shared credentials/revocation are instance-independent, but Shiny
sessions and the existing media cache still reside within an individual instance.

## Separate publication service

Use `Dockerfile.publication`: it includes **only** the access layer, publication
entry point, Starlette and Uvicorn. It contains no working outputs, pipeline code,
documentation bundle or Shiny application. The service always requires the `paper`
role, even if a team credential is accidentally included in its configuration.

Create a separate access-secret JSON containing only the publication credential,
publication shares and a different signing key. Use a **dedicated service account**
with Secret Accessor only on that publication secret and Storage Object Viewer
only on the publication bucket. Do not grant it project-wide storage roles or
mount the working bucket. Keep the bucket private; files are served through the
viewer. Treat the paper's published password as public.

```powershell
docker build -f Dockerfile.publication -t REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/dpv-publication:VERSION .
docker push REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/dpv-publication:VERSION

gcloud storage buckets add-iam-policy-binding gs://PUBLICATION_BUCKET --member=serviceAccount:PUBLICATION_SA --role=roles/storage.objectViewer --project=PROJECT_ID
gcloud secrets create dpv-publication-access --replication-policy=user-managed --locations=REGION --data-file=outputs/dashboard/private/publication-access.json --project=PROJECT_ID
gcloud secrets add-iam-policy-binding dpv-publication-access --member=serviceAccount:PUBLICATION_SA --role=roles/secretmanager.secretAccessor --project=PROJECT_ID

gcloud run deploy PUBLICATION_SERVICE --image REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/dpv-publication:VERSION --project PROJECT_ID --region REGION --service-account PUBLICATION_SA --allow-unauthenticated --set-env-vars DPV_ACCESS_CONFIG=/secrets/dpv/access.json,DPV_SHARE_ROOT=/mnt/publication --set-secrets /secrets/dpv/access.json=dpv-publication-access:latest --add-volume mount-path=/mnt/publication,type=cloud-storage,bucket=PUBLICATION_BUCKET,readonly=true
```

Publish the service's landing-page URL and paper access ID/code. Do not put a
password in the URL. A stable custom domain can preserve the paper's link across
future service changes.

## Local development

```powershell
$env:DPV_ACCESS_CONFIG = "$PWD/outputs/dashboard/private/access.json"
$env:DPV_SHARE_ROOT = "$PWD/outputs/shared-releases"
$env:DPV_ACCESS_INSECURE_LOCAL = '1' # only for localhost HTTP
.\start-dashboard.ps1
```

Explicit local development bypass is available with `DPV_ACCESS_DEV_BYPASS=1`.
Both bypass and insecure cookies are refused when Cloud Run's `K_SERVICE` is set;
publication services refuse bypass too. Do not use bypass on a network listener.

## Validation

`dpv_dashboard/tests/test_access.py` covers login, CSRF, role boundaries, direct
file/media/static routes, scoped downloads, credential rotation, cross-instance
cookies, failed configuration, escaped previews, publication-only roles, logout,
idle WebSocket revocation and Cloud Run configuration guards. Symlink coverage
requires an OS account allowed to create symlinks. Run alongside the existing
dashboard tests. Live GCP secret mounts, bucket IAM, image builds and a deployed
browser session still require deployment validation with your chosen resources.

Local verification on 2026-10-19: 34 access tests passed; one symlink test was
skipped because Windows denied symlink creation. The combined dashboard suite
reported 101 passed, one skipped and three failures in the unchanged chat-profile
tests. Those three failures reproduced when that test module ran on its own.
The real Shiny entry point was confirmed wrapped, and importing the publication
entry point was confirmed not to import Shiny or the working app. Docker image
builds were not run because the Docker daemon was unavailable. No GCP resources,
real credentials or secrets were created or changed.

Sources: [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets),
[Cloud Storage mounts](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts),
[Cloud Run WebSockets](https://docs.cloud.google.com/run/docs/triggering/websockets).

## Current deployment checkpoint: research-dpv

On 2026-10-19, the prepared access configuration was uploaded as version 1 of
`dpv-dashboard-access`, using user-managed replication in `us-east1`. Automatic
replication was rejected by this project's resource-location organization policy.
Do not rerun the secret-creation command for this existing secret. Future changes
use `gcloud secrets versions add` after the local configuration is updated.

The runtime access grant failed because the active UCF identity lacks
`secretmanager.secrets.setIamPolicy`. The existing runtime has project Editor,
which does not include reading secret payloads. A project administrator with
permission to manage this secret's IAM policy must run:

```powershell
gcloud secrets add-iam-policy-binding dpv-dashboard-access --project research-dpv --member "serviceAccount:908142717267-compute@developer.gserviceaccount.com" --role roles/secretmanager.secretAccessor
```

That grant is no longer needed for the selected bucket-file approach described
at the top of this guide. The access configuration is now stored at
`gs://research-dpv-kw-outputs/private/access.json` and mounted read-only at
`/mnt/dpv-access/access.json`, with metadata caches disabled. Research outputs
remain mounted at `/app/outputs`; `private` is reserved from result migration.

Cloud Build `55d7d7a9-6d1d-4e53-bf3f-7723fbf63849` succeeded and revision
`kw-dashboard-00004-qiz` is ready, with the `access-check` verification tag.
The focused access/discovery suite passed 37 tests, with one Windows symlink test
skipped. After explicit production-cutover approval, `kw-dashboard-00004-qiz`
now serves 100% of traffic and Google IAP is disabled. The existing URL is
`https://kw-dashboard-62j6rzjsdq-ue.a.run.app`. Live HTTPS checks confirmed the
application login page, Secure/HttpOnly/SameSite cookies and login redirects for
seven protected routes, including media, documentation, downloads and private
configuration. The checks used no user passwords. Existing credentials were not
changed. Collaborator/publication file grants remain empty pending approval.

Google's IAP-disable command warned that it could not remove the old IAP service
agent's Invoker binding. The service-level IAP setting is nevertheless disabled,
and live requests reach the app's login page without Google authentication.
