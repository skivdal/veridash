import './App.css';
import { useAccount } from 'jazz-tools/react-core';
import { MyAppAccount, TodoItem } from './schema';
import { AuthStateIndicator } from './AuthStateIndicator';
import { useState, useRef } from 'react';
import { getFileByHash, storeFile, ConnectionManager, WebSocketSignalingConnection } from './util/fileTransfer';

function App() {
  const [draft, setDraft] = useState("");
  const fileUpload = useRef<HTMLInputElement | null>(null);

  const [myId, setMyId] = useState("");
  const [peerId, setPeerId] = useState("");

  const { me } = useAccount(MyAppAccount, {
    resolve: {
      profile: true,
      root: true,
    },
  });

  if (!me) {
    return <div>Loading...</div>;
  }

  return (
    <>
      <p>Hello, {me.profile.name}</p>

      <AuthStateIndicator />

      <ul>
        {me.root.todos?.map(item => {
          if (!item) return;
          return <li key={item.id}>{item.title} {item.completed ? "(completed)" : ""}</li>
        })}
      </ul>

      <input type="text" value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button type="button" onClick={() => {
        if (!me.root || !me.root.todos) return;
        me.root.todos.push(TodoItem.create({ title: draft, completed: false }));
      }}>Add</button>

      <br />
      <br />
      <br />
      <br />

      <input type="file" ref={fileUpload} />
      <button type="button" onClick={async () => {
        if (fileUpload.current != null) {
          const result = await storeFile(fileUpload.current);
          console.log(result);

          if (result != null)
            console.log(await getFileByHash(result.hash));
        }
      }}>"Upload"</button>

      <br />
      <br />
      <br />
      <br />

      <input type="text" value={myId} onChange={(e) => setMyId(e.target.value)} />
      <input type="text" value={peerId} onChange={(e) => setPeerId(e.target.value)} />
      <button type="button" onClick={async () => {
        const sig = new WebSocketSignalingConnection(myId, peerId);
        const mgr = new ConnectionManager(sig);
        console.log(mgr);
      }}>Connect</button>
    </>
  );
}

export default App;

