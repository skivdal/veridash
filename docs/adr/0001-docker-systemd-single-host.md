# ADR 0001: Docker containers supervised directly by systemd

Status: accepted

## Context

VeriDash initially runs on one VPS with an attached NVIDIA GPU. The application
processes need reproducible Python and media-tool environments, while PostgreSQL,
TLS, static files, and the filesystem blob store are more straightforward as
host-managed services. Docker's NVIDIA runtime is already the least surprising GPU
integration path for this host.

## Decision

API, scheduler, CPU-worker, and GPU-worker release images are immutable OCI images.
Explicit systemd units invoke `docker run`; Docker Compose is not a production
control plane. PostgreSQL, Nginx/TLS, static SPA files, blob storage, and backups
remain host-managed. A separate one-shot migration image owns dbmate and migrations.

Only the API has an HTTP listener, bound to host loopback through Docker host
networking. Worker and scheduler containers publish no ports. Containers run as a
fixed non-root UID, drop capabilities, enable `no-new-privileges`, use read-only root
filesystems, receive bounded tmpfs mounts, and never mount the Docker socket.
The API trusts forwarded client addresses only from loopback Nginx, which supplies
the configured server name rather than an untrusted incoming Host value.

Production image references must include an OCI digest. The release image contains
a build-derived FFmpeg/FFprobe fingerprint. Ansible supplies that same value to all
three applications; mismatched fingerprints fail closed rather than enabling cache
reuse under an ambiguous tool revision.

## Consequences

Systemd remains the single service supervisor and can independently restart or roll
back each process. GPU workers can use `--gpus all` without a second container
runtime. Host networking gives containers access to loopback PostgreSQL, so process
hardening and application-level authorization remain important. Moving to multiple
hosts would require revisiting host networking and the filesystem BlobStore.
