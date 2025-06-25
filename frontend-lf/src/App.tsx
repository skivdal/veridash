import './App.css';
import { useAccount } from 'jazz-tools/react-core';
import { MyAppAccount, TodoItem } from './schema';
import { AuthStateIndicator } from './AuthStateIndicator';
import { useState, useRef, useEffect } from 'react';
import { getFileByInfo, storeFile, WebSocketSignalingConnection, RTCFileTransfer, type FileTransferError, type FileTransferSuccess } from './util/fileTransfer';

function App() {
  const [draft, setDraft] = useState("");
  const fileUpload = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [myId, setMyId] = useState("");
  const [peerId, setPeerId] = useState("");
  const [uploadInfo, setUploadInfo] = useState("");
  const [downloadInfo, setDownloadInfo] = useState("");
  const [downloadMsg, setDownloadMsg] = useState("");
  const [displayFile, setDisplayFile] = useState<File | undefined>();

  useEffect(() => {
    if (!displayFile || !videoRef.current) return;

    const objectURL = URL.createObjectURL(displayFile);
    videoRef.current.src = objectURL;

    return () => {
      URL.revokeObjectURL(objectURL);
    };
  }, [displayFile]);

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
      }}>Add todo</button>

      <br />
      <br />
      <br />
      <br />

      <input type="file" ref={fileUpload} />
      <button type="button" onClick={async () => {
        if (fileUpload.current != null) {
          const result = await storeFile(fileUpload.current);
          if (result != null) {
            setUploadInfo(JSON.stringify(result));
          } else {
            setUploadInfo("Something went wrong storing that file");
          }
        }
      }}>Store in OPFS</button>
      <br />
      <pre>{uploadInfo}</pre>

      <br />
      <br />
      <br />
      <br />

      <input type="text" value={myId} onChange={(e) => setMyId(e.target.value)} />
      <input type="text" value={peerId} onChange={(e) => setPeerId(e.target.value)} />
      <br />
      <input type="text" value={downloadInfo} onChange={(e) => setDownloadInfo(e.target.value)} />

      <button type="button" onClick={async () => {
        const sig = new WebSocketSignalingConnection(myId, peerId);
        const mgr = new RTCFileTransfer(sig);
        if (downloadInfo != "") {
          await mgr.channelReady();
          mgr.requestFile(JSON.parse(downloadInfo), 0, async (result) => {
            if ("errorReason" in result) {
              const err = result as FileTransferError;
              setDownloadMsg(`Error: ${err.errorReason}.\nGot ${err.successfulBytes} bytes of data`);
            } else {
              const res = result as FileTransferSuccess;
              setDownloadMsg(`Success!\nGot ${res.successfulBytes} bytes of data in ${res.timeSeconds}s`);

              const file = await getFileByInfo(JSON.parse(downloadInfo))
              setDisplayFile(file);
            }
          });
        }
      }}>Connect</button>

      <br />
      <pre>{downloadMsg}</pre>

      <br />
      <video ref={videoRef} style={{ maxHeight: "50vh", maxWidth: "75vw" }} controls />

    </>
  );
}

export default App;

