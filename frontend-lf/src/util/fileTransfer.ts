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

async function getWritable(hash: string): Promise<FileSystemWritableFileStream> {
  const root = await navigator.storage.getDirectory();
  const fileHandle = await root.getFileHandle(hash, { create: true });
  return fileHandle.createWritable();
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
    const writable = await getWritable(hash);
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

export async function getFileByInfo(info: FileInfo): Promise<File> {
  const root = await navigator.storage.getDirectory();
  const fileHandle = await root.getFileHandle(info.hash);
  const file = await fileHandle.getFile();
  return new File([file], info.name, { type: info.type });
}

export async function haveFile(info: FileInfo): Promise<boolean> {
  const file = await getFileByInfo(info);
  const hash = await hashStream(file.stream());
  return hash == info.hash && file.size == info.size;
}

interface SignalingConnection {
  clientReady: () => void;
  serverReady: (callback: () => void) => void;

  polite: boolean;

  announceCandidate: (cand: RTCIceCandidate) => void;
  sendSDP: (sdp: RTCSessionDescription | null) => void;

  listenCandidate: (callback: (cand: RTCIceCandidate) => void) => void;
  listenSDP: (callback: (sdp: RTCSessionDescription) => void) => void;

  close: () => void;
}

export class WebSocketSignalingConnection implements SignalingConnection {
  private ws: WebSocket
  private myId: string;
  private peerId: string;
  polite: boolean;

  constructor(myId: string, peerId: string) {
    this.myId = myId;
    this.peerId = peerId;
    this.polite = this.myId < this.peerId;

    this.ws = new WebSocket("ws://localhost:8080");

    this.ws.addEventListener("error", event => console.error("Signaling Websocket error:", event));
    this.ws.addEventListener("close", event => console.log("Signaling Websocket closed:", event));
  }

  close() {
    this.ws.close();
  }

  clientReady() {
    this.ws.send(JSON.stringify({ type: "join", id: this.myId }));
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
    this.ws.send(JSON.stringify({ type: "signal", to: this.peerId, data }));
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

function uint8ArrayToBase64(arr: Uint8Array): string {
  const binaryString = String.fromCharCode(...arr);
  return btoa(binaryString);
}

function base64ToUint8Array(str: string): Uint8Array {
  const binaryString = atob(str);
  const length = binaryString.length;
  const uint8Array = new Uint8Array(length);
  for (let i = 0; i < length; i++) {
    uint8Array[i] = binaryString.charCodeAt(i);
  }
  return uint8Array;
}

function toUrlSafeBase64(str: string) {
  return str.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromUrlSafeBase64(str: string) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  const padding = '='.repeat((4 - (str.length % 4)) % 4);
  return str + padding;
}

export type FileTransferResult = FileTransferError | FileTransferSuccess
export type FileTransferError = { errorReason: string, successfulBytes: number }
export type FileTransferSuccess = { successfulBytes: number, timeSeconds: number }

type FileTransferMessage = FileTransferRequest | FileTransferResponse | FileTransferPacket
type FileTransferRequest = { type: "FileTransferRequest", info: FileInfo, startByte: number, endByte: number }
type FileTransferResponse = { type: "FileTransferResponse", info: FileInfo } & ({ accepted: true } | { accepted: false, reason: string })
type FileTransferPacket = { startByte: number, dataBase64: string }

/** WARN: can only handle one active transfer at a time, on either side of the transaction */
export class RTCFileTransfer {
  private pc: RTCPeerConnection | undefined;
  private signal: SignalingConnection;
  private channel: RTCDataChannel | undefined;
  private channelOpen = false;
  private earlyIceCand: RTCIceCandidate[] = [];  // buffer ICE candidates until remoteDescription is received

  // variables for WebRTC perfect-negotiation
  private makingOffer = false;
  // (polite is part of SignalingConnection)

  constructor(signal: SignalingConnection) {
    this.signal = signal;
    this.signal.serverReady(async () => await this.establishConnection());
  }

  close() {
    if (this.channel)
      this.channel.close();

    if (this.pc)
      this.pc.close();

    this.signal.close();
  }

  // NOTE: this is a very hacky way of doing things, no rejection on error
  async channelReady(): Promise<void> {
    return new Promise<void>(resolve => {
      const id = setInterval(() => {
        if (this.channelOpen) {
          clearInterval(id);
          resolve();
        }
      }, 100);
    });
  }

  private async establishConnection() {
    const config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
    this.pc = new RTCPeerConnection(config);

    this.signal.listenCandidate(async (cand: RTCIceCandidate) => {
      if (!this.pc || !this.pc.remoteDescription) {
        this.earlyIceCand.push(cand);
        return;
      }

      await this.pc.addIceCandidate(cand);
    });

    this.signal.listenSDP(async (sdp: RTCSessionDescription) => {
      if (!this.pc)
        return;

      const readyForOffer =
        !this.makingOffer &&
        (this.pc.signalingState === "stable" || this.pc.signalingState === "have-local-offer");

      const ignoreOffer = sdp.type === "offer" && !readyForOffer && !this.signal.polite;
      if (ignoreOffer)
        return;

      await this.pc.setRemoteDescription(sdp);
      while (this.earlyIceCand.length) { // flush ICE candidates found before remote desc
        await this.pc.addIceCandidate(this.earlyIceCand.shift());
      }
      if (sdp.type === "offer") {
        await this.pc.setLocalDescription(await this.pc.createAnswer());
        this.signal.sendSDP(this.pc.localDescription);
      }
    });

    this.pc.ondatachannel = (e) => {
      if (this.channel) return;
      this.channel = e.channel;
      this.wireChannel();
    };

    // This triggers first when the datachannel is created (i.e. only on the polite client)
    this.pc.onnegotiationneeded = async () => {
      if (!this.pc) return;

      try {
        this.makingOffer = true;
        await this.pc.setLocalDescription(await this.pc.createOffer());
        this.signal.sendSDP(this.pc.localDescription);
      } finally {
        this.makingOffer = false;
      }
    };

    // Forward disovered candidates to signaling server
    this.pc.onicecandidate = ({ candidate }) => {
      if (candidate) {
        this.signal.announceCandidate(candidate);
      }
    };

    this.pc.onconnectionstatechange = () => {
      if (this.pc) {
        console.log("WebRTC connection State:", this.pc.connectionState);
      }
    };

    // Announce ready to signaling server
    this.signal.clientReady();

    // The polite party creates the data channel
    if (this.signal.polite) {
      this.channel = this.pc.createDataChannel("fileData");
      this.wireChannel();
    }
  }

  private wireChannel() {
    if (!this.channel) {
      return;
    }

    this.channel.onmessage = async (e) => { await this.handleMessage(e); }
    this.channel.onopen = () => {
      this.channelOpen = true;
      console.log("WebRTC channel open");
    };
    this.channel.onclose = () => {
      this.channelOpen = false;
      console.log("WebRTC channel closed. Not reopening");
      this.close();
    }
  }

  private async handleMessage(e: MessageEvent<any>) {
    const data: FileTransferMessage = JSON.parse(e.data);
    if (!("type" in data && data.type === "FileTransferRequest") || !this.channel) {
      return;
    }

    const req = data as FileTransferRequest;

    // Do we have the file according to spec?
    let requestOk = false;
    try {
      await requestPersistentStorage();
      const exists = await haveFile(req.info);
      if (exists) {
        requestOk = true;
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "NotFoundError")) {
        const err: FileTransferResponse = {
          type: "FileTransferResponse",
          info: req.info,
          accepted: false,
          reason: "Unknown error",
        };
        this.channel.send(JSON.stringify(err));
        this.channel.close();

        throw e;
      }
    }

    if (!requestOk) {
      const err: FileTransferResponse = {
        type: "FileTransferResponse",
        info: req.info,
        accepted: false,
        reason: "I don't have the requested file",
      };
      this.channel.send(JSON.stringify(err));
      this.channel.close();

      return;
    }

    // Send accept message
    const acceptMsg: FileTransferResponse = { type: "FileTransferResponse", info: req.info, accepted: true };
    this.channel.send(JSON.stringify(acceptMsg));

    // Send the file
    const highWaterMark = 4 * 1024 * 1024  // 4 MiB max in-flight
    this.channel.bufferedAmountLowThreshold = highWaterMark / 2;

    const chunkSize = 64 * 1024;  // 64 KiB
    const file = await getFileByInfo(req.info);
    let offset = req.startByte;

    while (offset < req.endByte) {
      // Relieve channel pressure
      if (this.channel.bufferedAmount > highWaterMark) {
        await new Promise<void>((resolve, reject) => {
          if (!this.channel) {
            reject("channel disappeared whilst waiting for packets to be sent???");
            return;
          }

          this.channel.addEventListener("bufferedamountlow", () => resolve(), { once: true });
        });
      }

      // Enqueue next slice
      const next = Math.min(chunkSize, req.endByte - offset);

      const slice = file.slice(offset, offset + next);
      const data = new Uint8Array(await slice.arrayBuffer());
      const message: FileTransferPacket = { startByte: offset, dataBase64: toUrlSafeBase64(uint8ArrayToBase64(data)) }

      console.log(`Sending packet of size ${data.length}`);
      this.channel.send(JSON.stringify(message));
      offset += next;
    }
  };

  async requestFile(info: FileInfo, startByte: 0, callback: ((res: FileTransferResult) => void)) {
    // Error: no connection
    if (this.channel?.readyState != "open") {
      callback({ errorReason: "No connection to peer", successfulBytes: 0 });
      return;
    }

    // Success(?): we already have the file
    try {
      await requestPersistentStorage();
      const exists = await haveFile(info);
      if (exists) {
        callback({ successfulBytes: info.size, timeSeconds: 0 });
        this.close();
        return;
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "NotFoundError")) {
        throw e;
      }
    }

    const startTime = new Date().getTime() / 1000;
    let bytesReceived = 0;
    const endByte = info.size;
    const bytesExpected = endByte - startByte;

    const writable = await getWritable(info.hash);

    // Register handlers
    this.channel.onmessage = async (e) => {
      const data: FileTransferMessage = JSON.parse(e.data);
      if ("type" in data && data.type == "FileTransferResponse") {
        const res = data as FileTransferResponse;
        if (!res.accepted) {
          callback({ successfulBytes: 0, errorReason: res.reason });
          this.close();
        }
      } else if (!("type" in data)) {
        const pkt = data as FileTransferPacket;

        const bytes = base64ToUint8Array(fromUrlSafeBase64(pkt.dataBase64));

        // atomic
        await writable.write({
          type: "write",
          position: pkt.startByte,
          data: bytes,
        });

        bytesReceived += bytes.length;
        console.log(`Received ${bytes.length} bytes of ${info.name}`);

        if (bytesReceived == bytesExpected) {
          const curTime = new Date().getTime() / 1000;
          await writable.close();  // needs to be called to save

          if (await haveFile(info)) {
            callback({ successfulBytes: bytesReceived, timeSeconds: curTime - startTime });
          } else {
            // TODO: remove the created file?
            callback({
              successfulBytes: bytesReceived,
              errorReason: "Error writing file or corrupted at transit",
            });
          }
          this.close();
        } else if (bytesReceived > bytesExpected) {
          callback({
            successfulBytes: bytesReceived,
            errorReason: `Got more bytes than expected. Expected: ${bytesExpected}`,
          });
          await writable.abort();
          this.close();
        }
      }
    };

    this.channel.addEventListener("error", (e) => {
      // If connection breaks, the user should initiate a new request, starting from where the previous left off.
      callback({ successfulBytes: bytesReceived, errorReason: e.error.message });
      this.close();
    });

    // Send request
    const req: FileTransferRequest = { type: "FileTransferRequest", info, startByte, endByte };
    this.channel.send(JSON.stringify(req));
  }
}

