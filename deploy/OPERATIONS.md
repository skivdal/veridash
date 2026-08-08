# VeriDash single-host operations

The initial production shape is one Debian VPS: PostgreSQL, Nginx/TLS, static web
files, and backups run on the host; the API, scheduler, CPU worker, optional GPU
worker, and one-shot migrations run as immutable containers supervised by systemd.
Docker Compose is not a production control plane.

## Build a release

Run all checks before producing artifacts:

```sh
uv run poe ci:all
pnpm --dir web check
pnpm --dir web build
```

Build the image targets from the repository root, push them to the selected
registry, and resolve their repository digests. Never deploy a mutable tag.

```sh
docker build --target api -t REGISTRY/veridash-api:RELEASE .
docker build --target scheduler -t REGISTRY/veridash-scheduler:RELEASE .
docker build --target worker -t REGISTRY/veridash-worker:RELEASE .
docker build --target worker-gpu -t REGISTRY/veridash-worker-gpu:RELEASE .
docker build --target migration -t REGISTRY/veridash-migration:RELEASE .
```

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

The vault must define `vault_veridash_database_password`. The inventory must use
digest-qualified image references and a unique release ID. Keep inventory and vault
files outside Git; the relevant conventional paths are ignored.

Provision a new server from the repository root:

```sh
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/site.yml \
  --ask-vault-pass
```

For later releases, build `web/dist`, update release ID and digests, then run:

```sh
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/deploy.yml \
  --ask-vault-pass
```

The deployment sequence pulls images, verifies immutable media-tool identity,
installs the static release, renders restricted environment files, applies dbmate
migrations once, restarts services, and waits for the loopback health endpoint.
Nginx is the only public application listener. The containers do not receive the
Docker socket, and only API/workers receive the blob-store mount.

Useful checks:

```sh
systemctl status veridash-api veridash-scheduler veridash-worker-cpu
journalctl -u veridash-api -u veridash-scheduler -u veridash-worker-cpu -f
curl --fail http://127.0.0.1:8000/api/health
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
  veridash-worker-gpu
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
