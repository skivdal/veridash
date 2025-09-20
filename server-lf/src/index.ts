import 'dotenv/config'
import { serve } from '@hono/node-server'
import { Hono } from 'hono'
import { auth } from './auth.js'
import worker from './worker.js'

const app = new Hono()

app.on(["POST", "GET"], "/api/auth/**", (c) => auth.handler(c.req.raw))

serve({
  fetch: app.fetch,
  port: 9090
}, (info) => {
  console.log(`Server is running on http://localhost:${info.port}`)
})
