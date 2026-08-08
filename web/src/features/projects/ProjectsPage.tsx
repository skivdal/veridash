const foundationItems = [
  "Static React and Vite application",
  "Durable FastAPI and PostgreSQL architecture",
  "Dependency-aware Python analysis workers",
] as const;

export function ProjectsPage() {
  return (
    <div className="app-canvas">
      <header className="app-header">
        <a className="brand" href="/" aria-label="VeriDash home">
          <span className="brand-mark" aria-hidden="true">
            V
          </span>
          <span>VeriDash</span>
        </a>
        <span className="build-label">Rebuild foundation</span>
      </header>

      <main className="page-shell">
        <section className="intro-card" aria-labelledby="projects-title">
          <p className="eyebrow">Video forensics workspace</p>
          <h1 id="projects-title">Projects</h1>
          <p className="intro-copy">
            The new durable project workspace is being built on a clean, typed
            foundation.
          </p>

          <ul className="foundation-list">
            {foundationItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
