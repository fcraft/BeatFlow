import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:3090'

async function loginAndGetFile(page, request) {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { username: 'admin', password: 'Admin123!' },
  })
  const { access_token } = await resp.json()
  await page.goto('/')
  await page.evaluate((token) => localStorage.setItem('token', token), access_token)

  const projectsResp = await request.get(`${API_BASE}/api/v1/projects/`, {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  const projects = await projectsResp.json()
  if (!projects[0]) return { token: access_token, fileId: null }

  const filesResp = await request.get(`${API_BASE}/api/v1/projects/${projects[0].id}/files?limit=1`, {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  const files = await filesResp.json()
  return { token: access_token, fileId: files[0]?.id ?? null }
}

test.describe('FileViewerView — Mobile', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('mobile'), 'Desktop-only skip')

  let fileId: string | null

  test.beforeEach(async ({ page, request }) => {
    const result = await loginAndGetFile(page, request)
    fileId = result.fileId
    if (!fileId) {
      test.skip()
      return
    }
    await page.goto(`/files/${fileId}`)
    await page.waitForLoadState('networkidle')
  })

  test('file icon is responsive (smaller on mobile)', async ({ page }) => {
    const icon = page.locator('.rounded-xl').first()
    const box = await icon.boundingBox()
    if (!box) {
      test.skip()
      return
    }
    expect(box.width).toBeLessThanOrEqual(48)
  })

  test('mobile bottom toolbar is visible', async ({ page }) => {
    const toolbar = page.locator('text=下载').last()
    await expect(toolbar).toBeVisible()
  })

  test('desktop action buttons are hidden on mobile', async ({ page }) => {
    const desktopDownload = page.locator('.btn-secondary:has-text("下载")')
    await expect(desktopDownload).toBeHidden()
  })
})
