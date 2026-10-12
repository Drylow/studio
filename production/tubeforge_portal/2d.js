/** Same-origin TubeForge gateway. Existing portal auth is the only member login. */
import fs from 'node:fs/promises'
import path from 'node:path'
import { Readable, Transform } from 'node:stream'
import { pipeline } from 'node:stream/promises'

const PREFIX = '/api/2d'
const FILE = process.env.TUBEFORGE_CONNECTION_FILE || path.join(process.cwd(), 'data', 'tubeforge-worker.json')
const UPLOAD_LIMIT = 100 * 1024 * 1024

export function workerPath(raw) {
  const pathname = String(raw || '').split('?')[0]
  let decoded
  try { decoded = decodeURIComponent(pathname) } catch { throw new Error('Invalid TubeForge path') }
  if (decoded.includes('\\') || decoded.split('/').some(p => p === '.' || p === '..') || !/^\/(api(?:\/|$)|media\/|style-media\/|legacy\.html$|app\.js$|style\.css$|workspace\.js$|workspace\.css$|exemple(?:_tiktok)?\.csv$|fonts\/|assets\/)/.test(decoded)) {
    throw new Error('Invalid TubeForge path')
  }
  return String(raw)
}

export default function mount2D(app, auth) {
  app.use(PREFIX, auth, async (req, res) => {
    let controller
    try {
      const target = workerPath(req.url)
      if (!['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'].includes(req.method)) return res.status(405).json({error:'Method not allowed'})
      const origin = req.get('origin')
      if (!['GET','HEAD','OPTIONS'].includes(req.method) && (req.get('sec-fetch-site') === 'cross-site' || origin && new URL(origin).host !== req.get('host'))) {
        return res.status(403).json({error:'Cross-site requests are not allowed.'})
      }
      const connection = JSON.parse(await fs.readFile(FILE, 'utf8'))
      const base = new URL(connection.base_url)
      if (base.protocol !== 'https:' || base.username || base.password || !connection.token || connection.token.length < 32) throw new Error('Invalid private worker connection')
      const member = {id:String(req.user.id), name:String(req.user.name || req.user.id).slice(0,100)}
      const headers = {'Accept-Encoding':'identity','X-Worker-Token':connection.token,'X-TubeForge-Member':Buffer.from(JSON.stringify(member)).toString('base64url')}
      for (const key of ['accept','range','content-type','if-range']) if (req.headers[key]) headers[key] = req.headers[key]
      let body
      if (!['GET','HEAD','OPTIONS'].includes(req.method)) {
        if (req.rawBody) body = req.rawBody
        else if (req.is('application/json')) body = JSON.stringify(req.body || {})
        else if (req.headers['content-length'] === '0') body = undefined
        else {
          if (Number(req.headers['content-length']) > UPLOAD_LIMIT) return res.status(413).json({error:'Upload exceeds 100 MB.'})
          let bytes = 0
          const limiter = new Transform({transform(chunk, encoding, done) {
            bytes += chunk.length
            if (bytes > UPLOAD_LIMIT) { const error = new Error('Upload exceeds 100 MB.'); error.code = 'UPLOAD_TOO_LARGE'; done(error) }
            else done(null, chunk)
          }})
          req.on('error', error => limiter.destroy(error))
          body = req.pipe(limiter)
        }
      }
      controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 650000)
      const close = () => { if (!res.writableFinished) controller.abort() }
      res.on('close', close)
      try {
        const upstream = await fetch(base.origin + base.pathname.replace(/\/$/,'') + target, {
          method:req.method, headers, body, duplex:'half', signal:controller.signal, redirect:'manual'
        })
        // No upstream cookie, credential, private URL or redirect is returned to browsers.
        if (upstream.status >= 300 && upstream.status < 400) return res.status(502).json({error:'Unexpected TubeForge redirect.'})
        res.status(upstream.status)
        res.setHeader('Cache-Control','private, no-store')
        for (const key of ['content-type','content-range','accept-ranges','content-disposition']) {
          const value = upstream.headers.get(key); if (value) res.setHeader(key,value)
        }
        if (target.split('?')[0] === '/legacy.html' && req.method === 'GET' && upstream.ok) {
          let html = await upstream.text()
          html = html.replace(/(src|href)="\/(app\.js|style\.css)"/g, '$1="'+PREFIX+'/$2"')
          html = html.replace('</head>', `<script>window.TUBEFORGE_BASE=${JSON.stringify(PREFIX)}</script></head>`)
          return res.send(html)
        }
        const length = upstream.headers.get('content-length')
        if (length) res.setHeader('Content-Length',length)
        if (!upstream.body || req.method === 'HEAD') return res.end()
        await pipeline(Readable.fromWeb(upstream.body),res)
      } finally { clearTimeout(timeout); res.off('close',close) }
    } catch (error) {
      controller?.abort()
      if (res.headersSent) return res.destroy()
      const invalid = error.message === 'Invalid TubeForge path'
      res.status(invalid ? 400 : error.code === 'UPLOAD_TOO_LARGE' ? 413 : 502).json({error:invalid ? error.message : 'TubeForge is temporarily unavailable. Try again shortly.'})
    }
  })
}
