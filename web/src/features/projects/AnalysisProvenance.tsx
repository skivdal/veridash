import type {
  AnalysisArtifactResponse,
  AnalysisJobResponse,
} from "../../api/generated/schemas";

export function AnalysisProvenance({
  artifacts = [],
  job,
}: {
  artifacts?: AnalysisArtifactResponse[];
  job: AnalysisJobResponse;
}) {
  const unpinnedTools = Object.entries(job.implementation_fingerprints ?? {})
    .filter(([, value]) => value === "deployment-unpinned")
    .map(([name]) => name);
  const displayedArtifacts =
    artifacts.length <= 12
      ? artifacts
      : [
          ...artifacts.filter((artifact) => artifact.kind === "json"),
          ...artifacts
            .filter((artifact) => artifact.kind !== "json")
            .slice(0, 8),
        ].slice(0, 12);
  return (
    <details className="analysis-provenance">
      <summary>Provenance and parameters</summary>
      <dl>
        <div>
          <dt>Module</dt>
          <dd>
            <code>
              {job.module_id}@{job.implementation_version}
            </code>
          </dd>
        </div>
        <div>
          <dt>Result schema</dt>
          <dd>Version {job.result_schema_version}</dd>
        </div>
        <div>
          <dt>Execution</dt>
          <dd>
            {job.reused ? "Reused immutable result" : "Executed for this job"}
          </dd>
        </div>
        <div>
          <dt>Attempts</dt>
          <dd>{job.attempts.length}</dd>
        </div>
      </dl>
      <div className="provenance-parameters">
        <strong>Parameters</strong>
        <code>{JSON.stringify(job.parameters)}</code>
      </div>
      {unpinnedTools.length > 0 ? (
        <p className="provenance-warning">
          The deployed build for {unpinnedTools.join(", ")} is not pinned yet;
          cross-project cache reuse is disabled for this result.
        </p>
      ) : !job.cacheable ? (
        <p className="provenance-warning">
          Cross-project cache reuse is disabled for this module version.
        </p>
      ) : null}
      {artifacts.length > 0 ? (
        <ul className="provenance-artifacts">
          {displayedArtifacts.map((artifact) => (
            <li key={artifact.id}>
              <span>{artifact.output_name}</span>
              <code title={artifact.sha256_hex}>
                {artifact.schema_id}@{artifact.schema_version} ·{" "}
                {artifact.sha256_hex.slice(0, 12)}…
              </code>
            </li>
          ))}
          {artifacts.length > displayedArtifacts.length ? (
            <li>
              <span>
                +{artifacts.length - displayedArtifacts.length} additional
                immutable outputs
              </span>
            </li>
          ) : null}
        </ul>
      ) : null}
    </details>
  );
}
