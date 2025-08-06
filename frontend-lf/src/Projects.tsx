import { useRef, useState } from "react";
import { useOldBackend } from "./util/oldBackend";
import { co } from "jazz-tools";
import { useAccount } from 'jazz-tools/react-core';
import { FileInfo, MyAppAccount, Project } from './schema';
import { BackendMessage } from "./backendSchema";

function Projects() {
  const { me } = useAccount(MyAppAccount, {
    resolve: {
      profile: true,
      root: true,
    },
  });

  const nameInput = useRef<HTMLInputElement>(null);
  const activeProject = useRef<co.loaded<typeof Project> | undefined>(undefined);

  const [doListen, setDoListen] = useState(false);
  useOldBackend("wss://veridash.fotoverifier.eu/ws", activeProject.current?.id, doListen);

  return (
    <>
      <h1>Projects</h1>

      <button onClick={() => {
        setDoListen(!doListen);
      }}>
        {doListen ? "Deactivate WebSocket" : "Activate WebSocket"}
      </button>

      <br />
      <br />

      <input ref={nameInput} type="text"></input>
      <button onClick={() => {
        const proj = Project.create({
          name: nameInput.current?.value ?? "Unnamed project",
          files: co.list(FileInfo).create([]), 
          jobState: co.list(BackendMessage).create([]), 
        });

        if (me) {
          me.root.projects?.push(proj);
          activeProject.current = proj;
        } else {
          console.error("No me found");
        }
      }}>New</button>

      <ul>
        {me && me.root.projects?.map(p => {
          if (p)
            return <li key={p.id}>
              <span
                onClick={async () => {
                  const pr = await Project.load(p.id);
                  console.log(pr);
                  if (pr) {
                    activeProject.current = pr;
                  }
                }}
                style={{
                  color: "blue", textDecoration: "underline", cursor: "pointer"
                }}>
                {p.name}
              </span> ({p.id})
            </li>
        })}
      </ul>

      <pre>
        {JSON.stringify(activeProject.current?.toJSON(), null, 2)}
      </pre>
    </>
  );
}

export default Projects;

