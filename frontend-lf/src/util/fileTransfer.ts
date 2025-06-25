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
  private ws: WebSocket
  private listeners: { type: string, handler: EventListenerOrEventListenerObject | null }[] = [];
  private myId: string;
  private peerId: string;

  constructor(myId: string, peerId: string) {
    this.myId = myId;
    this.peerId = peerId;

    this.ws = new WebSocket("ws://localhost:8080");

    this.ws.addEventListener("error", event => console.error("Signaling Websocket error:", event));
    this.ws.addEventListener("close", event => console.warn("Signaling Websocket closed:", event));
  }

  close() {
    this.ws.close();
  }

  clientReady() {
    this.ws.send(JSON.stringify({ type: 'join', id: this.myId }));
  }

  serverReady(callback: () => void) {
    if (this.ws.readyState == WebSocket.OPEN) {
      callback();
      return;
    }

    const handleOpen = () => {
      callback();
      this.ws.removeEventListener("open", handleOpen);
    }

    this.ws.addEventListener("open", handleOpen);
  }

  announceCandidate(cand: RTCIceCandidate) {
    this.sendSignal({ candidate: cand });
  }

  sendSDP(sdp: RTCSessionDescription | null) {
    this.sendSignal({ sdp });
  }

  private sendSignal(data: any) {
    this.ws.send(JSON.stringify({ type: 'signal', to: this.peerId, data }));
  }

  listenCandidate(callback: (cand: RTCIceCandidate) => void) {
    this.ws.addEventListener("message", (event) => {
      // @ts-ignore
      const { from, data } = JSON.parse(event.data);
      if (!data.candidate || from != this.peerId) {
        return;
      }

      const cand = new RTCIceCandidate(data.candidate);
      callback(cand);
    });
  }

  listenSDP(callback: (sdp: RTCSessionDescription) => void) {
    this.ws.addEventListener("message", (event) => {
      // @ts-ignore
      const { from, data } = JSON.parse(event.data);
      if (!data.sdp || from != this.peerId) {
        return;
      }

      const sdp = new RTCSessionDescription(data.sdp);
      callback(sdp);
    });
  }
}

export class RTCFileTransfer {
  private pc: RTCPeerConnection | undefined;
  private signal: SignalingConnection;
  private channel: RTCDataChannel | undefined;

  constructor(signal: SignalingConnection) {
    this.signal = signal;
    this.signal.serverReady(async () => await this.establishConnection());
  }

  close() {
    if (this.pc)
      this.pc.close();
    this.signal.close();
  }

  private async establishConnection() {
    const config = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
    this.pc = new RTCPeerConnection(config);

    this.signal.listenCandidate(async (cand: RTCIceCandidate) => {
      if (!this.pc)
        return;

      await this.pc.addIceCandidate(cand);
    });

    this.signal.listenSDP(async (sdp: RTCSessionDescription) => {
      if (!this.pc)
        return;

      await this.pc.setRemoteDescription(sdp);
      if (sdp.type === 'offer') {
        const answer = await this.pc.createAnswer();
        await this.pc.setLocalDescription(answer);
        this.signal.sendSDP(this.pc.localDescription);
      }
    });

    // Announce ready to signaling server
    this.signal.clientReady();

    // Forward disovered candidates to signaling server
    this.pc.onicecandidate = ({ candidate }) => {
      if (candidate)
        this.signal.announceCandidate(candidate);
    };

    // Handle connection events
    this.pc.onconnectionstatechange = () => {
      if (this.pc)
        console.log('Connection State:', this.pc.connectionState);
    }

    // Channel opened from the other end
    this.pc.ondatachannel = (event) => {
      this.channel = event.channel;
      this.channel.onmessage = (e) => console.log('Received:', e.data);
      this.channel.onopen = () => console.log('Channel open');
    };

    // Create channel and handle channel events
    this.channel = this.pc.createDataChannel('chat');
    this.channel.onopen = () => console.log('Channel open');
    this.channel.onmessage = (e) => console.log('Received:', e.data);

    // Create and signal my offer
    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);
    this.signal.sendSDP(this.pc.localDescription);
  }
}

