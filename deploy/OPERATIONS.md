# VeriDash single-host operations

The initial production shape is one Debian VPS: PostgreSQL, Nginx/TLS, static web
files, and backups run on the host; the API, scheduler, CPU worker, optional GPU and
translation workers, and one-shot migrations run as immutable containers supervised
by explicit Docker-based systemd units. This deployment does not use Compose or
Podman Quadlets.

## Build a release

GitHub Actions is the release builder. Every pull request and push runs the Python,
database, generated-code, frontend, production-build, and Ansible syntax checks,
then builds all six Dockerfile targets for `linux/amd64`. Builds from pull requests
and ordinary branches are not pushed.

Pushes to `main`, `v*` tags, the temporary deployment branch `rebuild-s26`, and
manually dispatched trusted runs additionally publish and provenance-attest these
packages. Remove the deployment-branch exception after the initial cutover:

- `ghcr.io/skivdal/veridash-api`
- `ghcr.io/skivdal/veridash-scheduler`
- `ghcr.io/skivdal/veridash-worker`
- `ghcr.io/skivdal/veridash-worker-gpu`
- `ghcr.io/skivdal/veridash-worker-translation`
- `ghcr.io/skivdal/veridash-migration`

Each image job writes its digest-qualified reference to the GitHub Actions job
summary. The checks job also uploads `web/dist` as a static frontend artifact named
for the commit SHA. Download that artifact before running Ansible and deploy only
the image digests, never the convenience `latest`, version, or `sha-*` tags.

If the GHCR packages are private, authenticate Docker on the VPS once with a
fine-grained credential that can only read packages. Do not put the token in the
inventory or a systemd environment file:

```sh
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io --username GITHUB_USER --password-stdin
```

The GitHub workflow uses its short-lived `GITHUB_TOKEN` with `packages: write`; it
does not require a long-lived registry secret.

The three Python images contain the same exact FFmpeg/FFprobe fingerprint. Ansible
checks this before migrations or restarts and passes it to every process. That
fingerprint becomes part of the analysis implementation version and enables safe
cross-project result reuse. Local unpinned processes remain deliberately
non-cacheable for FFmpeg-backed analyses.

## Provision and deploy

Install the declared collections and create a private inventory from the example:

```sh
ansible-galaxy collection install -r ansible/requirements.yml
cp ansible/inventory/hosts.example.yml ansible/inventory/hosts.yml
ansible-vault create ansible/inventory/group_vars/all/vault.yml
```

The tested Ansible core and collection versions are recorded in
`tools/versions.env`; use those versions on the control host.

The vault must define `vault_veridash_database_password`. Enabling translation also
requires `vault_veridash_openai_api_key`, the digest-qualified translation-worker
image, and `veridash_enable_translation_worker: true`. The provider credential is
rendered only into that worker's restricted environment file. The inventory must
use digest-qualified image references and a unique release ID. Keep inventory and
vault files outside Git; the relevant conventional paths are ignored.

Provision a new server from the repository root:

```sh
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/site.yml \
  --ask-vault-pass
```

For a coexistence migration, prepare only the host and PostgreSQL first, while the
legacy proxy remains active and before release images are available:

```sh
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/prepare.yml \
  --vault-password-file ansible/.vault-password
```

The later `site.yml` run is idempotent and applies the application, proxy, and
backup roles after the staged release inputs are ready.

The database role defaults to setting its password only when the role is created,
which avoids PostgreSQL generating a new salted hash on every idempotence run. To
rotate it, change the vaulted password, temporarily set
`veridash_database_no_password_changes: false`, run the deployment once, then
restore the default `true` value.

For later releases, download the CI-built frontend artifact into `web/dist`, update
the release ID and all image digests, then run:

```sh
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy.yml \
  --ask-vault-pass
```

The deployment sequence pulls images, verifies immutable media-tool identity,
installs the static release, renders restricted environment files, applies dbmate
migrations once, restarts services, waits for the dependency-aware loopback
readiness endpoint, and asserts that the host-network API has exactly one listener
bound to 127.0.0.1. Nginx is the only public application listener. The containers
do not receive the Docker socket, no container publishes a Docker port, and only
API/workers receive the blob-store mount. This listener assertion is an important
boundary: Docker port publication and wildcard listeners can bypass the intended
UFW policy.

The host role installs Docker, PostgreSQL, Nginx, Certbot, and UFW. It deliberately
does not install NVIDIA drivers or NVIDIA Container Toolkit. The VPS image and the
operator own that host-specific setup.

On a host with a dedicated persistent data disk, containerd may store its root at
`/var/lib/veridash/containerd` instead of consuming the operating-system disk. Stop
Docker and containerd before copying `/var/lib/containerd`, set containerd's
top-level `root` setting to that path, and install
`deploy/containerd-veridash.conf` as
`/etc/systemd/system/containerd.service.d/veridash-data.conf`. The systemd drop-in
prevents containerd from starting unless the VeriDash data filesystem is mounted.
Keep the original runtime root until the migrated daemon and every existing
container have been verified, then remove that superseded copy.

Useful checks:

```sh
systemctl status veridash-api veridash-scheduler veridash-worker-cpu \
  veridash-worker-translation
journalctl -u veridash-api -u veridash-scheduler -u veridash-worker-cpu \
  -u veridash-worker-translation -f
curl --fail http://127.0.0.1:8000/api/ready
ss -H -ltn 'sport = :8000'
nginx -t
```

The GPU image adds the pinned CUDA 12/cuDNN 9 runtime libraries required by
Faster-Whisper. If GPU execution is enabled, first install and verify NVIDIA
Container Toolkit on the VPS, provide the digest-qualified `worker-gpu` image, set
`veridash_enable_gpu_worker: true`, and inspect:

```sh
systemctl status veridash-worker-gpu
docker run --rm --gpus all nvidia/cuda:VERSION-base nvidia-smi
```

Use a deliberately selected, pinned CUDA image for that diagnostic.

Deployment downloads the exact `Systran/faster-whisper-medium` revision into the
host data root before starting the GPU worker. Analysis children use that local
snapshot with network downloads disabled. A missing or mismatched model becomes a
durable configuration failure rather than an implicit download during a job.

Translation uses a dedicated networked worker pool with concurrency one by default.
Its OpenAI credential is not supplied to the API, scheduler, CPU worker, GPU worker,
or unrelated analysis child processes. Transcript batches are sent only after local
transcription completes; source transcripts remain independently available if
translation is queued or fails.

## Bootstrap and manage administrators

On a fresh installation, create the first administrator after migrations complete.
Run the CLI inside the exact deployed API image; it prompts twice for the password:

```sh
docker run --rm --network host --pull never \
  --env-file /etc/veridash/api.env \
  --entrypoint veridash-admin \
  ghcr.io/skivdal/veridash-api@sha256:REPLACE \
  create-user ADMIN_USERNAME ADMIN_EMAIL --admin
```

Accounts that existed before the user-administration migration are promoted to
administrator so an upgrade retains access. An administrator gets a **Users** link
in the application header. The dashboard creates non-administrator accounts from a
username, email address, and initial password; it lists last-login time and total
project count and can deactivate those users. Deactivation immediately revokes all
of that user's sessions. Administrator deactivation remains a server-operator task
to prevent accidental lockout.

VeriDash does not send account email and has no self-service registration or
password reset. An operator can reset a forgotten password locally with
`veridash-admin reset-password USERNAME`; doing so also revokes existing sessions.

## Backup and restore

Primary projects and blobs are retained indefinitely. Local recovery snapshots
have a separate, configurable retention period (30 days by default) and are created
daily by `veridash-backup.timer`. A real deployment also needs an encrypted,
off-host copy of `/var/backups/veridash`; local snapshots do not protect against VPS
loss.

Run and inspect a snapshot:

```sh
systemctl start veridash-backup.service
journalctl -u veridash-backup.service
readlink -f /var/backups/veridash/latest
```

The snapshot contains a validated custom-format PostgreSQL dump, immutable blobs,
and checksummed manifests. It intentionally excludes runtime secrets.

Restoration replaces the database and is therefore deliberately manual. Put the
site into maintenance, stop every application service, and invoke the explicit
confirmation interface:

```sh
systemctl stop veridash-api veridash-scheduler veridash-worker-cpu \
  veridash-worker-gpu veridash-worker-translation
/usr/local/sbin/veridash-restore --confirm \
  /var/backups/veridash/snapshots/YYYYMMDDTHHMMSSZ
systemctl start veridash-api veridash-scheduler veridash-worker-cpu
```

The restore program refuses if an application service is active. It checks the dump,
manifest, and every blob hash before recreating the database. It merges snapshot
blobs without deleting unrelated primary files. Afterward, verify the health route,
login, one known project, and one media range request before reopening traffic.

## Rollback and failure boundaries

Static releases remain in `/opt/veridash/releases`. Container images are addressed
by digest. To roll application code back, restore the previous release ID and image
digests in inventory and run the deploy playbook. Database migrations are forward
only unless a migration explicitly documents a safe rollback; never point older
code at a schema it cannot understand. If a migration crossed that boundary, use a
verified pre-release snapshot instead.

Worker failures are persisted as typed public errors plus private diagnostic IDs.
Inspect server logs by diagnostic ID. Do not expose stderr, credentials, filesystem
paths, or model-provider responses to the browser. Retry only failures classified as
transient or stalled; invalid media and internal bugs require operator/user action.
