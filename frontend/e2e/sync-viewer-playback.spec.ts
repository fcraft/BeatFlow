import { test, expect, type APIRequestContext, type Page } from '@playwright/test'

const API_BASE = 'http://localhost:3090'

async function loginAsAdmin(page: Page) {
  const resp = await page.request.post(`${API_BASE}/api/v1/auth/login`, {
    data: {
      email: 'admin@beatflow.com',
      password: 'Admin123!',
    },
  })

  if (!resp.ok()) {
    throw new Error(`Login failed: ${resp.status()} ${await resp.text()}`)
  }

  const data = await resp.json()
  const token = data.access_token

  await page.goto('/')
  await page.evaluate((t) => {
    localStorage.setItem('token', t)
    localStorage.setItem('auth', JSON.stringify({
      token: t,
      user: { username: 'admin', email: 'admin@beatflow.com', role: 'admin' },
    }))
  }, token)

  return token as string
}

async function createProject(request: APIRequestContext, token: string, name: string): Promise<string> {
  const resp = await request.post(`${API_BASE}/api/v1/projects/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name,
      description: 'Sync viewer playback E2E project',
    },
  })
  expect(resp.ok()).toBeTruthy()
  const data = await resp.json()
  return data.id
}

async function deleteProject(request: APIRequestContext, token: string, projectId: string) {
  await request.delete(`${API_BASE}/api/v1/projects/${projectId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

async function generateTestWav(): Promise<Buffer> {
  const sampleRate = 44100
  const duration = 2.0
  const freq = 440
  const numSamples = Math.floor(duration * sampleRate)
  const samples = new Int16Array(numSamples)

  for (let i = 0; i < numSamples; i++) {
    const t = i / sampleRate
    const value = Math.sin(2 * Math.PI * freq * t) * 0.5
    samples[i] = Math.max(-32768, Math.min(32767, Math.floor(value * 32767)))
  }

  const dataSize = samples.byteLength
  const buffer = Buffer.alloc(44 + dataSize)
  buffer.write('RIFF', 0)
  buffer.writeUInt32LE(36 + dataSize, 4)
  buffer.write('WAVE', 8)
  buffer.write('fmt ', 12)
  buffer.writeUInt32LE(16, 16)
  buffer.writeUInt16LE(1, 20)
  buffer.writeUInt16LE(1, 22)
  buffer.writeUInt32LE(sampleRate, 24)
  buffer.writeUInt32LE(sampleRate * 2, 28)
  buffer.writeUInt16LE(2, 32)
  buffer.writeUInt16LE(16, 34)
  buffer.write('data', 36)
  buffer.writeUInt32LE(dataSize, 40)

  const dataView = new DataView(buffer.buffer, buffer.byteOffset + 44, dataSize)
  for (let i = 0; i < numSamples; i++) {
    dataView.setInt16(i * 2, samples[i], true)
  }

  return buffer
}

async function uploadTestFile(request: APIRequestContext, token: string, projectId: string, filename: string) {
  const wavBuffer = await generateTestWav()
  const resp = await request.post(`${API_BASE}/api/v1/projects/${projectId}/files/upload`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      file: {
        name: filename,
        mimeType: 'audio/wav',
        buffer: wavBuffer,
      },
    },
  })
  expect(resp.ok()).toBeTruthy()
  const data = await resp.json()
  return data.id as string
}

async function createAssociation(request: APIRequestContext, token: string, projectId: string, ecgFileId: string, pcgFileId: string) {
  const resp = await request.post(`${API_BASE}/api/v1/associations/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      project_id: projectId,
      ecg_file_id: ecgFileId,
      pcg_file_id: pcgFileId,
      pcg_offset: 0,
    },
  })
  expect(resp.ok()).toBeTruthy()
  const data = await resp.json()
  return data.id as string
}

test.describe('SyncViewer 起播定位', () => {
  let token = ''
  let projectId = ''
  let associationId = ''
  let pcgFileId = ''

  test.beforeAll(async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
      data: { email: 'admin@beatflow.com', password: 'Admin123!' },
    })
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    token = data.access_token

    projectId = await createProject(request, token, `SyncViewer Play ${Date.now()}`)
    const ecgFileId = await uploadTestFile(request, token, projectId, 'sync-ecg.wav')
    pcgFileId = await uploadTestFile(request, token, projectId, 'sync-pcg.wav')
    associationId = await createAssociation(request, token, projectId, ecgFileId, pcgFileId)
  })

  test.afterAll(async ({ request }) => {
    if (projectId) {
      await deleteProject(request, token, projectId)
    }
  })

  test('下载接口支持 HTTP Range，供媒体 seek 使用', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/v1/files/${pcgFileId}/download?token=${token}`, {
      headers: { Range: 'bytes=0-99' },
    })

    expect(resp.status()).toBe(206)
    expect(resp.headers()['accept-ranges']).toBe('bytes')
    expect(resp.headers()['content-range']).toMatch(/^bytes 0-99\/\d+$/)
  })

  test('拖动到目标位置后立即播放，也会从目标时间起播', async ({ page }) => {
    await page.addInitScript(() => {
      const state = new WeakMap<HTMLMediaElement, {
        currentTime: number
        pendingTime: number
        seeking: boolean
        paused: boolean
      }>()

      const ensureState = (media: HTMLMediaElement) => {
        if (!state.has(media)) {
          state.set(media, { currentTime: 0, pendingTime: 0, seeking: false, paused: true })
        }
        return state.get(media)!
      }

      ;(window as any).__mediaLog = []
      const log = (entry: Record<string, unknown>) => {
        ;(window as any).__mediaLog.push(entry)
      }

      Object.defineProperty(HTMLMediaElement.prototype, 'duration', {
        configurable: true,
        get() {
          return 2
        },
      })

      Object.defineProperty(HTMLMediaElement.prototype, 'readyState', {
        configurable: true,
        get() {
          return HTMLMediaElement.HAVE_METADATA
        },
      })

      Object.defineProperty(HTMLMediaElement.prototype, 'seeking', {
        configurable: true,
        get() {
          return ensureState(this).seeking
        },
      })

      Object.defineProperty(HTMLMediaElement.prototype, 'paused', {
        configurable: true,
        get() {
          return ensureState(this).paused
        },
      })

      Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', {
        configurable: true,
        get() {
          return ensureState(this).currentTime
        },
        set(value: number) {
          const media = this as HTMLMediaElement
          const s = ensureState(media)
          s.pendingTime = value
          s.seeking = true
          log({ type: 'set-currentTime', tag: media.tagName.toLowerCase(), value })

          setTimeout(() => {
            s.currentTime = s.pendingTime
            s.seeking = false
            media.dispatchEvent(new Event('seeked'))
            media.dispatchEvent(new Event('canplay'))
          }, 30)
        },
      })

      HTMLMediaElement.prototype.load = function () {}
      HTMLMediaElement.prototype.pause = function () {
        ensureState(this).paused = true
      }
      HTMLMediaElement.prototype.play = function () {
        const s = ensureState(this)
        s.paused = false
        log({ type: 'play', tag: this.tagName.toLowerCase(), currentTime: s.currentTime })
        return Promise.resolve()
      }
    })

    await loginAsAdmin(page)
    await page.goto(`/sync/${associationId}`)

    const syncCard = page.locator('div.card').filter({ has: page.getByText('同步播放') }).first()
    await expect(syncCard).toBeVisible()

    const progressBar = syncCard.locator('div.relative.h-3.bg-gray-100.rounded-full.cursor-pointer.mb-4.select-none').first()
    const box = await progressBar.boundingBox()
    expect(box).toBeTruthy()
    if (!box) throw new Error('progress bar not found')

    await page.mouse.click(box.x + box.width * 0.62, box.y + box.height / 2)
    await page.locator('body').click()

    const playButton = syncCard.locator('button').first()
    await playButton.click()

    await page.waitForTimeout(120)

    const mediaLog = await page.evaluate(() => (window as any).__mediaLog as Array<Record<string, number | string>>)
    const audioSetEvents = mediaLog.filter((entry) => entry.tag === 'audio' && entry.type === 'set-currentTime')
    const audioPlayEvent = mediaLog.find((entry) => entry.tag === 'audio' && entry.type === 'play')

    expect(audioSetEvents.length).toBeGreaterThan(0)
    expect(audioPlayEvent).toBeTruthy()

    const targetTime = Number(audioSetEvents[audioSetEvents.length - 1].value)
    expect(targetTime).toBeGreaterThan(1)
    expect(Number(audioPlayEvent?.currentTime)).toBeCloseTo(targetTime, 1)
  })
})
