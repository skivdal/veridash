# VeriDash repository guidance

For any rebuild or architecture work, read `docs/rebuild-plan.md` before changing
code. It is the current proposed source of truth and records the recovered design,
existing analysis graph, target architecture, implementation phases, open product
and deployment decisions, and acceptance criteria.

The current `frontend/` and `backend/` are legacy behavior references.
`figma-recover/` is an imperfect, potentially untracked reconstruction used for
visual and interaction archaeology. Do not repair, relocate, delete, or import it
wholesale unless a task specifically requests that work.

Important rebuild invariants:

- The web application is a static React/TypeScript/Vite SPA: no SSR, React Server
  Components, or production Node application server.
- The initial product has one username/password user, one source video per project,
  indefinite retention, and no collaboration or simultaneous note editing.
- Successful upload automatically creates the standard analysis DAG exactly once.
  Stitching remains explicit because the user selects its ordered frame inputs.
- The server owns project, job, dependency, result, progress, and event state. A
  component mount must never schedule analysis.
- Analysis methods use typed, versioned Python module contracts and declare all
  cache-affecting inputs, dependencies, parameters, tools, models, and prompts.
- Progress, heartbeats, leases, attempts, typed errors, and artifact publication are
  execution concerns around independently testable analysis kernels.
- Preserve provenance and human judgment; never turn model output or missing
  metadata into an unsupported authenticity verdict.
- Never add automated video/frame summarization, question answering, frame captions,
  or generative metadata interpretation. Translation is the only permitted external
  model-provider use; reverse-image search remains a normal browser context action.
- Target the single VPS: enforce a global maximum of two concurrent GPU attempts and
  configure CPU concurrency independently.
- Use the root `uv` workspace and lockfile. Runnable processes belong in
  `apps/api`, `apps/scheduler`, and `apps/worker`; shared side-effect-free packages
  belong in `libs`. A runnable app must not import another runnable app.
- Use dbmate plain-SQL migrations and SQLc-generated async queriers. Never hand-edit
  generated SQLc code, never use an ORM as the domain model, and never run migrations
  from an application import/startup or worker process.
- Use pnpm and its frozen lockfile for the Vite SPA. REST clients and TanStack Query
  hooks are generated with Orval from committed OpenAPI; generated files are not
  edited manually.
- Use Ruff, strict basedpyright, pytest, and Poe as the repository command surface;
  keep fast tests independent of PostgreSQL and model weights.
- Implement and verify one end-to-end vertical slice at a time, including refresh,
  reconnect, and failure behavior.

If an implementation decision changes the plan, update the plan or add an ADR in
the same change.
