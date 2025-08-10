import { useRef, useState } from "react";
import { useOldBackend } from "./util/oldBackend";
import { co } from "jazz-tools";
import { useAccount, useCoState } from 'jazz-tools/react-core';
import { FileInfo, MyAppAccount, Project } from './schema';
import { BackendMessage } from "./backendSchema";
import { storeFile } from "./util/fileTransfer";

function Projects() {
  const { me } = useAccount(MyAppAccount, {
    resolve: {
      profile: true,
      root: {
        projects: true,
      },
    },
  });

  const nameInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const [activeProjectId, setActiveProjectId]= useState<string | undefined>(undefined);
  const activeProject = useCoState(Project, activeProjectId, {
    resolve: true,
  });

  const [doListen, setDoListen] = useState(false);
  useOldBackend("wss://veridash.fotoverifier.eu/ws", activeProjectId, doListen);

  return (
    <>
      <h1>Projects</h1>

      <button type="button" onClick={() => {
        setDoListen(!doListen);
      }}>
        {doListen ? "Deactivate WebSocket" : "Activate WebSocket"}
      </button>

      <br />
      <br />

      <label htmlFor="projectName">Project Name: </label>
      <input ref={nameInput} type="text" name="projectName"></input>
      <br />

      <label htmlFor="projectVideo">Project Video: </label>
      <input ref={fileInput} type="file" name="projectVideo"></input>
      <br />
      <br />

      <button type="button" onClick={async () => {
        if (!fileInput.current?.files)
          return;

        const fi = await storeFile(fileInput.current);
        if (!fi)
          return;

        const proj = Project.create({
          name: nameInput.current?.value ?? "Unnamed project",
          files: co.list(FileInfo).create([fi]),
          jobState: co.list(BackendMessage).create([]),
        });

        if (me) {
          me.root.projects?.push(proj);
          setActiveProjectId(proj.id);
        } else {
          console.error("No me found");
        }
      }}>
        Create new project
      </button>

      <br />
      <br />

      <p>Existing projects:</p>
      <ul>
        {me?.root.projects?.map(p => {
          if (p)
            return <li key={p.id}>
              <span
                onClick={async () => {
                  setActiveProjectId(p.id);
                }}
                style={{
                  color: "blue", textDecoration: "underline", cursor: "pointer"
                }}>
                {p.name}
              </span> ({p.id})
            </li>
        })}
      </ul>

      { activeProject &&
        <>
          <br />
          <p>Info for selected project "{ activeProject?.name }"</p>
          <pre>
            {JSON.stringify(activeProject?.toJSON(), null, 2)}
          </pre>
        </>
      }
    </>
  );
}

export default Projects;

