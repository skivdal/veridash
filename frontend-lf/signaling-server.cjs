// Dummy Signaling Server for WebRTC connections.
// DO NOT USE IN PRODUCTION. It does no authentication.

const WebSocket = require("ws");

const wss = new WebSocket.Server({ port: 8080 });
const peers = new Map();

wss.on('connection', (ws) => {
  let userId;

  ws.on('message', (message) => {
    const msg = JSON.parse(message);
    if (msg.type === 'join') {
      userId = msg.id;
      peers.set(userId, ws);
    } else if (msg.type === 'signal') {
      const target = peers.get(msg.to);
      if (target) {
        target.send(JSON.stringify({ from: userId, data: msg.data }));
      }
    }
  });

  ws.on('close', () => {
    if (userId)
      peers.delete(userId);
  });
});

