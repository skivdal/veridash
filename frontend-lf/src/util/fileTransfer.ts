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
  /** SHA256 hex string */
  hash: string;
}

export async function storeFile(fileInput: HTMLInputElement): Promise<FileInfo | null> {
  if (!fileInput.files || fileInput.files.length === 0) {
    console.warn("No file selected");
    return null;
  }

  const file = fileInput.files[0];
  const { name, size } = file;

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

  return { name, size, hash };
}

