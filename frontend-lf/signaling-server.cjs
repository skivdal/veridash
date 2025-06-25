// Dummy Signaling Server for WebRTC connections.
// DO NOT USE IN PRODUCTION. It does no authentication.

const WebSocket = require("ws");

const wss = new WebSocket.Server({ port: 8080 });
const peers = new Map();
const buffers = new Map();

wss.on('connection', (ws) => {
  let userId;

  ws.on('message', (message) => {
    const msg = JSON.parse(message);
    if (msg.type === 'join') {
      userId = msg.id;
      peers.set(userId, ws);

      if (!buffers.has(userId)) {
        return;
      }

      for (const serial of buffers.get(userId)) {
        ws.send(serial);
      }

      buffers.delete(userId);
    } else if (msg.type === 'signal') {
      const target = peers.get(msg.to);
      const serial = JSON.stringify({ from: userId, data: msg.data });

      if (target) {
        target.send(serial);
      } else {
        if (buffers.has(msg.to)) {
          buffers.get(msg.to).push(serial);
        } else {
          buffers.set(msg.to, [serial]);
        }
      }
    }
  });

  ws.on('close', () => {
    if (userId)
      peers.delete(userId);
  });
});

