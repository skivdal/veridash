# TODO

## Bring analysis data into Jazz project

- [x] Create schema
- [x] Old backend can fill schema
- [x] Project creation and selection
- [x] File upload to project
- [ ] Share project with other users
- [ ] Server-side client (backend integrates natively with Jazz)

## Getting P2P collaborative projects working

- [ ] Jazz as a signaling server (requires FileInfo as sharable Jazz object, connected to a project)
  - [ ] Needs authentication, some way of separating devices (for users with multiple)

- [ ] WebRTC connection graceful stop
  - [ ] Resume downloads properly
- [ ] Binary protocol when sending files
  - [ ] Make sure to include version header
- [ ] Figure out persistent storage permissions on Chrome (maybe Safari)

- [ ] Server-side client for video sharing (Node/Bun, must integrate with Jazz)

### Long-term

- [ ] Own STUN+TURN server (with auth for TURN)
- [ ] Download from multiple peers

