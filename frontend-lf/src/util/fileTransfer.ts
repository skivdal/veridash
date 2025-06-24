import { createSHA256 } from "hash-wasm";

// Actively asking for persistent storage permission greatly increases the quota
async function requestPersistentStorage(): Promise<boolean> {
  if (!navigator.storage || !navigator.storage.persist) {
    console.warn("Persistent storage API not supported");
    return false;
  }

  const isPersisted = await navigator.storage.persisted();
  if (isPersisted) {
    console.log("We already have permission for persistent storage");
    return true;
  }

  const granted = await navigator.storage.persist();
  if (granted) {
    console.log("Persistent storage granted");
  } else {
    console.warn("Persistent storage denied");
  }

  return granted;
}

async function hashStream(stream: ReadableStream<Uint8Array<ArrayBufferLike>>): Promise<string> {
  const hasher = await createSHA256();
  hasher.init();

  const reader = stream.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    hasher.update(value);
  }

  return hasher.digest("hex");
}

export type FileInfo = {
  name: string;
  size: number;
  /** MIME type */
  type: string;
  /** SHA256 hex string */
  hash: string;
}

export async function storeFile(fileInput: HTMLInputElement): Promise<FileInfo | null> {
  if (!fileInput.files || fileInput.files.length === 0) {
    console.warn("No file selected");
    return null;
  }

  const file = fileInput.files[0];
  const { name, size, type } = file;

  // Do some work while waiting for user
  const [_granted, hash] = await Promise.all([requestPersistentStorage(), hashStream(file.stream())]);

  {
    const root = await navigator.storage.getDirectory();
    const fileHandle = await root.getFileHandle(hash, { create: true });
    const writable = await fileHandle.createWritable();

    const reader = file.stream().getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      await writable.write(value);
    }
    await writable.close();
  }

  return { name, size, type, hash };
}

export async function getFileByHash(hash: string): Promise<File> {
  const root = await navigator.storage.getDirectory();
  const handle = await root.getFileHandle(hash);
  return handle.getFile();
}

interface SignalingConnection {
  clientReady: () => void;
  serverReady: (callback: () => void) => void;

  announceCandidate: (cand: RTCIceCandidate) => void;
  sendSDP: (sdp: RTCSessionDescription | null) => void;

  listenCandidate: (callback: (cand: RTCIceCandidate) => void) => void;
  listenSDP: (callback: (sdp: RTCSessionDescription) => void) => void;

  close: () => void;
}

export class WebSocketSignalingConnection implements SignalingConnection {
  _ws: WebSocket
  _listeners: { type: string, handler: EventListenerOrEventListenerObject | null }[] = [];
  _myId: string;
  _peerId: string;

  constructor(myId: string, peerId: string) {
    this._myId = myId;
    this._peerId = peerId;

    this._ws = new WebSocket("ws://localhost:8080");

    this._ws.addEventListener("error", event => console.error("Signaling Websocket error:", event));
    this._ws.addEventListener("close", event => console.warn("Signaling Websocket closed:", event));
  }

  close() {
    this._ws.close();
  }

  clientReady() {
    this._ws.send(JSON.stringify({ type: 'join', id: this._myId }));
  }

  serverReady(callback: () => void) {
    if (this._ws.readyState == WebSocket.OPEN) {
      callback();
      return;
    }

    const handleOpen = () => {
      callback();
      this._ws.removeEventListener("open", handleOpen);
    }

    this._ws.addEventListener("open", handleOpen);
  }

  announceCandidate(cand: RTCIceCandidate) {
    this._sendSignal({ candidate: cand });
  }

  sendSDP(sdp: RTCSessionDescription | null) {
    this._sendSignal({ sdp });
  }

  _sendSignal(data: any) {
    this._ws.send(JSON.stringify({ type: 'signal', to: this._peerId, data }));
  }

  listenCandidate(callback: (cand: RTCIceCandidate) => void) {
    this._ws.addEventListener("message", (event) => {
      // @ts-ignore
      const { from, data } = JSON.parse(event.data);
      if (!data.candidate || from != this._peerId) {
        return;
      }

      const cand = new RTCIceCandidate(data.candidate);
      callback(cand);
    });
  }

  listenSDP(callback: (sdp: RTCSessionDescription) => void) {
    this._ws.addEventListener("message", (event) => {
      // @ts-ignore
      const { from, data } = JSON.parse(event.data);
      if (!data.sdp || from != this._peerId) {
        return;
      }

      const sdp = new RTCSessionDescription(data.sdp);
      callback(sdp);
    });
  }
}

export class ConnectionManager {
  _pc: RTCPeerConnection | undefined;
  _signal: SignalingConnection;
  _channel: RTCDataChannel | undefined;

  constructor(signal: SignalingConnection) {
    this._signal = signal;
    this._signal.serverReady(async () => await this._establishConnection());
  }

  close() {
    if (this._pc)
      this._pc.close();
    this._signal.close();
  }

  async _establishConnection() {
    const config = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
    this._pc = new RTCPeerConnection(config);

    this._signal.listenCandidate(async (cand: RTCIceCandidate) => {
      if (!this._pc)
        return;

      await this._pc.addIceCandidate(cand);
    });

    this._signal.listenSDP(async (sdp: RTCSessionDescription) => {
      if (!this._pc)
        return;

      await this._pc.setRemoteDescription(sdp);
      if (sdp.type === 'offer') {
        const answer = await this._pc.createAnswer();
        await this._pc.setLocalDescription(answer);
        this._signal.sendSDP(this._pc.localDescription);
      }
    });

    // Announce ready to signaling server
    this._signal.clientReady();

    // Forward disovered candidates to signaling server
    this._pc.onicecandidate = ({ candidate }) => {
      if (candidate)
        this._signal.announceCandidate(candidate);
    };

    // Handle connection events
    this._pc.onconnectionstatechange = () => {
      if (this._pc)
        console.log('Connection State:', this._pc.connectionState);
    }

    // Channel opened from the other end
    this._pc.ondatachannel = (event) => {
      this._channel = event.channel;
      this._channel.onmessage = (e) => console.log('Received:', e.data);
      this._channel.onopen = () => console.log('Channel open');
    };

    // Create channel and handle channel events
    this._channel = this._pc.createDataChannel('chat');
    this._channel.onopen = () => console.log('Channel open');
    this._channel.onmessage = (e) => console.log('Received:', e.data);

    // Create and signal my offer
    const offer = await this._pc.createOffer();
    await this._pc.setLocalDescription(offer);
    this._signal.sendSDP(this._pc.localDescription);
  }
}

