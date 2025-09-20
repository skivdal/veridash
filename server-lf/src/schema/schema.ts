import { co, Group, z } from "jazz-tools";
import { BackendMessage } from "./backendSchema";

export const FileInfo = co.map({
  name: z.string(),
  size: z.number(),
  type: z.string(), // MIME type
  hash: z.string(), // SHA256 hex
});

export const Project = co.map({
  name: z.string(),
  description: z.string().optional(),
  files: co.list(FileInfo),
  jobState: co.list(BackendMessage),
});

export const Message = co.map({
  content: z.string(),
});

export const AccountRoot = co.map({
  projects: co.list(Project),
  status: co.feed(Message), // friends should read only from this
  fileTransfers: co.feed(Message), // friends should write only to this
});

export const MyAppAccount = co.account({
  root: AccountRoot,
  profile: co.map({ 
    name: z.string(),
    inbox: z.string().optional(),
  }),
}).withMigration(async (account) => {
  if (account.root === undefined) {
    const statusReaders = Group.create({ owner: account });
    const transferWriters = Group.create({ owner: account });
    account.root = AccountRoot.create({
      projects: co.list(Project).create([], account),
      status: co.feed(Message).create([], statusReaders),
      fileTransfers: co.feed(Message).create([], transferWriters),
    }, account);
  }
});
