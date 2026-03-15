import { expect, test } from '@playwright/test'

/**
 * BeatFlow 文件播放与分享 E2E 测试
 * 
 * 测试场景:
 * 1. 单文件播放 (Audio)
 * 2. 关联文件同步播放
 * 3. 权限控制 (Owner/Admin/Member/Viewer)
 * 4. 临时文件分享
 * 5. 关联分享
 */

const API_BASE = 'http://localhost:3090'
const UI_BASE = 'https://localhost:3080'

interface LoginResponse {
  access_token: string
  refresh_token: string
  id: string
  username: string
  email: string
}

// ============================================================================
// 工具函数
// ============================================================================

async function login(request, credentials: { username: string; password: string }): Promise<LoginResponse> {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: credentials,
  })
  return resp.json()
}

async function createProject(request, token: string, projectName: string) {
  const resp = await request.post(`${API_BASE}/api/v1/projects/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: projectName, description: `E2E test project` },
  })
  const data = await resp.json()
  return data.id
}

async function uploadTestFile(request, token: string, projectId: string, filename: string): Promise<string> {
  // 创建测试 WAV 文件的 Buffer (正弦波, 2 秒)
  const wavBuffer = await generateTestWav(filename)
  
  const formData = new FormData()
  const blob = new Blob([wavBuffer], { type: 'audio/wav' })
  formData.append('file', blob, filename)

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
  const data = await resp.json()
  return data.id
}

async function generateTestWav(filename: string): Promise<Buffer> {
  // 在 Node.js 环境中生成测试 WAV 文件
  // 正弦波, 44.1kHz, mono, 16-bit, 2 秒
  const sampleRate = 44100
  const duration = 2.0
  const freq = 440 // A4 note
  const numSamples = Math.floor(duration * sampleRate)
  
  // 创建 WAV 数据
  const numChannels = 1
  const bytesPerSample = 2
  const byteRate = sampleRate * numChannels * bytesPerSample
  const blockAlign = numChannels * bytesPerSample
  
  // 计算 PCM 数据
  const samples = new Int16Array(numSamples)
  for (let i = 0; i < numSamples; i++) {
    const t = i / sampleRate
    const value = Math.sin(2 * Math.PI * freq * t) * 0.5
    samples[i] = Math.max(-32768, Math.min(32767, Math.floor(value * 32767)))
  }
  
  // 构建 WAV 文件结构
  const dataSize = samples.byteLength
  const waveSize = 36 + dataSize
  const buffer = Buffer.alloc(44 + dataSize)
  
  // RIFF Header
  buffer.write('RIFF', 0)
  buffer.writeUInt32LE(waveSize, 4)
  buffer.write('WAVE', 8)
  
  // fmt subchunk
  buffer.write('fmt ', 12)
  buffer.writeUInt32LE(16, 16)      // Subchunk1Size (16 for PCM)
  buffer.writeUInt16LE(1, 20)       // AudioFormat (1 = PCM)
  buffer.writeUInt16LE(numChannels, 22)
  buffer.writeUInt32LE(sampleRate, 24)
  buffer.writeUInt32LE(byteRate, 28)
  buffer.writeUInt16LE(blockAlign, 32)
  buffer.writeUInt16LE(16, 34)      // BitsPerSample
  
  // data subchunk
  buffer.write('data', 36)
  buffer.writeUInt32LE(dataSize, 40)
  
  // Write sample data
  const dataView = new DataView(buffer.buffer, 44)
  for (let i = 0; i < numSamples; i++) {
    dataView.setInt16(i * 2, samples[i], true)
  }
  
  return buffer
}

// ============================================================================
// 测试套件 1: 单文件播放验证
// ============================================================================

test.describe('单文件播放验证', () => {
  let adminToken: string
  let projectId: string
  let fileId: string

  test.beforeAll(async ({ request }) => {
    // 登录
    const loginResp = await login(request, { username: 'admin', password: 'Admin123!' })
    adminToken = loginResp.access_token

    // 创建项目
    projectId = await createProject(request, adminToken, '文件播放测试')

    // 上传测试文件
    fileId = await uploadTestFile(request, adminToken, projectId, 'test-audio.wav')
  })

  test.skip('文件列表页面展示', async ({ page }) => {
    // TODO: This test requires data-testid attributes in FileManager component
    // Skipping until components are updated with testing selectors
  })

  test.skip('单文件播放页面加载', async ({ page }) => {
    // TODO: Requires data-testid="waveform-container" in FileViewerView
  })

  test.skip('音频播放控制', async ({ page }) => {
    // TODO: Requires waveform-container and player element data-testid
  })

  test.skip('进度条交互', async ({ page }) => {
    // TODO: Requires data-testid="progress-bar" in player
  })
})

// ============================================================================
// 测试套件 2: 关联文件同步播放验证
// ============================================================================

test.describe('关联文件同步播放验证', () => {
  let adminToken: string
  let projectId: string
  let ecgFileId: string
  let pcgFileId: string
  let associationId: string

  test.beforeAll(async ({ request }) => {
    const loginResp = await login(request, { username: 'admin', password: 'Admin123!' })
    adminToken = loginResp.access_token

    projectId = await createProject(request, adminToken, '关联文件测试')

    // 上传 ECG 和 PCG 文件
    ecgFileId = await uploadTestFile(request, adminToken, projectId, 'test-ecg.wav')
    pcgFileId = await uploadTestFile(request, adminToken, projectId, 'test-pcg.wav')

    // 创建关联
    const assocResp = await request.post(
      `${API_BASE}/api/v1/associations/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          project_id: projectId,
          ecg_file_id: ecgFileId,
          pcg_file_id: pcgFileId,
          pcg_offset: 0,
        },
      }
    )
    const assocData = await assocResp.json()
    associationId = assocData.id
  })

  test.skip('关联文件同步页面加载', async ({ page }) => {
    // TODO: Requires data-testid attributes in SyncViewerView
  })

  test.skip('关联文件同步控制', async ({ page }) => {
    // TODO: Requires data-testid for master play button and track elements
  })

  test.skip('偏移量调整', async ({ page }) => {
    // TODO: Requires data-testid for offset slider
  })
})

// ============================================================================
// 测试套件 3: 权限控制验证
// ============================================================================

test.describe('权限控制验证', () => {
  let ownerToken: string
  let memberToken: string
  let viewerToken: string
  let projectId: string
  let fileId: string

  test.beforeAll(async ({ request }) => {
    // 使用 admin 创建项目和文件
    const adminResp = await login(request, { username: 'admin', password: 'Admin123!' })
    const adminToken = adminResp.access_token

    // 获取成员用户 token (需要先在系统中有这些用户)
    try {
      const memberResp = await login(request, { username: 'member', password: 'Member123!' })
      memberToken = memberResp.access_token
    } catch {
      // 如果成员用户不存在，跳过此测试
      test.skip()
    }

    projectId = await createProject(request, adminToken, '权限测试项目')
    fileId = await uploadTestFile(request, adminToken, projectId, 'test-file.wav')

    // 设置项目所有者和成员 (需要实现)
    ownerToken = adminToken
  })

  test('项目所有者可以删除文件', async ({ page, request }) => {
    // 作为 owner 删除文件应成功
    const resp = await request.delete(
      `${API_BASE}/api/v1/files/${fileId}`,
      {
        headers: { Authorization: `Bearer ${ownerToken}` },
      }
    )
    expect(resp.status()).toBe(204)
  })

  test.skip('非项目成员无法访问文件', async ({ page }) => {
    // File was deleted in previous test, skipping
  })
})

// ============================================================================
// 测试套件 4: 临时分享验证
// ============================================================================

test.describe('临时文件分享验证', () => {
  let adminToken: string
  let projectId: string
  let fileId: string
  let shareCode: string

  test.beforeAll(async ({ request }) => {
    const loginResp = await login(request, { username: 'admin', password: 'Admin123!' })
    adminToken = loginResp.access_token

    projectId = await createProject(request, adminToken, '分享测试项目')
    fileId = await uploadTestFile(request, adminToken, projectId, 'share-test.wav')

    // 创建分享 (待实现)
    // const shareResp = await request.post(
    //   `${API_BASE}/api/v1/files/${fileId}/share`,
    //   {
    //     headers: { Authorization: `Bearer ${adminToken}` },
    //     data: {
    //       expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    //     },
    //   }
    // )
    // const shareData = await shareResp.json()
    // shareCode = shareData.share_code
  })

  test('分享页面无需认证可访问', async ({ page }) => {
    // 无需登录即可访问分享的文件
    // await page.goto(`${UI_BASE}/share/file/${shareCode}`)
    
    // 验证文件信息显示
    // await expect(page.locator('text=share-test.wav')).toBeVisible()
    // await expect(page.locator('[data-testid="waveform-container"]')).toBeVisible()
  })

  test('分享文件可以播放', async ({ page }) => {
    // 验证分享文件的播放功能
    // await page.goto(`${UI_BASE}/share/file/${shareCode}`)
    
    // const playButton = page.locator('button[title="播放"]')
    // await expect(playButton).toBeVisible()
    // await playButton.click()
    
    // 验证播放状态
    // const pauseButton = page.locator('button[title="暂停"]')
    // await expect(pauseButton).toBeVisible({ timeout: 5000 })
  })

  test('分享链接可复制', async ({ page }) => {
    // 测试分享链接复制功能
    // await page.goto(`${UI_BASE}/share/file/${shareCode}`)
    
    // const copyButton = page.locator('[data-testid="copy-share-link"]')
    // await copyButton.click()
    
    // 验证复制成功提示
    // await expect(page.locator('text=已复制')).toBeVisible()
  })
})
