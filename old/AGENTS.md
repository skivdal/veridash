# Archived implementation guidance

Everything below this directory is a read-only reference for the VeriDash rebuild.

- Do not repair, reformat, upgrade, lint, test, package, or deploy archived code as
  incidental work.
- Do not import archived Python or TypeScript modules from the rebuild.
- Consult the old implementation only to recover behavior, analysis algorithms,
  fixtures, assets, or visual intent requested by the active task.
- Implement recovered behavior anew under the repository root and preserve its
  provenance, error, progress, caching, and security contracts.
