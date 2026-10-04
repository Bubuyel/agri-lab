// node render.mjs preview 1,3,8,...      -> frames/preview-<t>.png
// node render.mjs video                  -> video2_silent.mp4 (1920x1080, 30 fps, from timing.json cues)
import puppeteer from 'puppeteer-core'
import { existsSync, mkdirSync, readFileSync } from 'node:fs'
import { spawn, execFileSync } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const mode = process.argv[2] ?? 'preview'
const FPS = 30
const b = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox', '--allow-file-access-from-files', '--hide-scrollbars'] })
const p = await b.newPage()
await p.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 })
await p.goto(pathToFileURL(path.join(here, 'scene2.html')).href, { waitUntil: 'load' })
await p.evaluate(() => document.fonts.ready)
await new Promise((r) => setTimeout(r, 800))
const TIMING = JSON.parse(readFileSync(path.join(here, 'timing2.json'), 'utf8'))
await p.evaluate((c) => window.setTiming(c), TIMING)
const total = TIMING.total

if (mode === 'preview') {
  mkdirSync(path.join(here, 'frames'), { recursive: true })
  for (const t of (process.argv[3] ?? '1').split(',').map(Number)) {
    await p.evaluate((x) => window.render(x), t)
    await p.screenshot({ path: path.join(here, 'frames', `walk-${t}.png`) })
  }
} else {
  const ff = execFileSync('python', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim()
  const out = path.join(here, 'video2_silent.mp4')
  const enc = spawn(ff, ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] })
  const n = Math.round(total * FPS)
  for (let i = 0; i < n; i++) {
    await p.evaluate((x) => window.render(x), i / FPS)
    const buf = await p.screenshot({ type: 'jpeg', quality: 96 })
    if (!enc.stdin.write(buf)) await new Promise((r) => enc.stdin.once('drain', r))
    if (i % 150 === 0) console.log(`frame ${i}/${n}`)
  }
  enc.stdin.end(); await new Promise((r) => enc.on('close', r))
  console.log('wrote', out)
}
await b.close()
