import { startWorker } from 'jazz-tools/worker';
import { MyAppAccount } from './schema/schema.js';

const { worker, experimental: { inbox } } = await startWorker({
  AccountSchema: MyAppAccount,
  syncServer: 'ws://localhost:4200',
  accountID: process.env.JAZZ_WORKER_ACCOUNT,
  accountSecret: process.env.JAZZ_WORKER_SECRET,
});

export default worker;
