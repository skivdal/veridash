import './App.css';
import { useAccount, useIsAuthenticated } from 'jazz-tools/react-core';
import { Message, MyAppAccount } from './schema';
import { AuthStateIndicator } from './AuthStateIndicator';
import { useState, useRef, useEffect } from 'react';
import { getFileByInfo, storeFile, WebSocketSignalingConnection, RTCFileTransfer, type FileTransferError, type FileTransferSuccess } from './util/fileTransfer';
import { AuthButton } from "./AuthButton.tsx";

function App() {
  const fileUpload = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [myId, setMyId] = useState("");
  const [peerId, setPeerId] = useState("");
  const [uploadInfo, setUploadInfo] = useState("");
  const [downloadInfo, setDownloadInfo] = useState("");
  const [downloadMsg, setDownloadMsg] = useState("");
  const [displayFile, setDisplayFile] = useState<File | undefined>();

  const inputNameRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!displayFile || !videoRef.current) return;

    const objectURL = URL.createObjectURL(displayFile);
    videoRef.current.src = objectURL;

    return () => {
      URL.revokeObjectURL(objectURL);
    };
  }, [displayFile]);

  const isAuthenticated = useIsAuthenticated();
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
      {isAuthenticated ? (
        <span>You're logged in.</span>
      ) : (
        <span>Authenticate to share the data with another device.</span>
      )}
      <AuthButton />

      <p>Hello, {me.profile.name}</p>

      <input type="text" ref={inputNameRef}></input>
      <button onClick={() => {
        if (!inputNameRef.current)
          return;

        me.profile.name = inputNameRef.current?.value;
      }}>Submit</button>

      <AuthStateIndicator />

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

      <br />
      <br />

      <button onClick={() => {
       me.root.status?.push(Message.create({
        content: "ping",
      }));
      }}>Add message</button>

      <pre>
        {JSON.stringify(me.root.status?.inCurrentSession, undefined, 2)}
      </pre>

    </>
  );
}

export default App;

