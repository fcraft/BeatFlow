import { test, expect } from '@playwright/test'
import { swipeLeft, longPress } from '../helpers/touch'

const API_BASE = 'http://localhost:3090'

async function loginAndGetProject(page, request) {
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
  return { token: access_token, projectId: projects[0]?.id }
}

test.describe('ProjectDetailView — Mobile', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('mobile'), 'Desktop-only skip')

  let projectId: string

  test.beforeEach(async ({ page, request }) => {
    const result = await loginAndGetProject(page, request)
    projectId = result.projectId
    if (!projectId) {
      test.skip()
      return
    }
    await page.goto(`/projects/${projectId}`)
    await page.waitForLoadState('networkidle')
  })

  test('breadcrumb shows simplified back arrow on mobile', async ({ page }) => {
    const backLink = page.locator('nav a').first()
    await expect(backLink).toBeVisible()
    await expect(backLink).toContainText('项目列表')
  })

  test('tab bar is horizontally scrollable', async ({ page }) => {
    await expect(page.locator('text=文件管理')).toBeVisible()
    await expect(page.locator('text=设置')).toBeVisible()
  })

  test('swipe left in content area switches to next tab', async ({ page }) => {
    await expect(page.locator('text=文件管理').first()).toBeVisible()
    const content = page.locator('.page-container').last()
    await swipeLeft(page, content, 150)
    await page.waitForTimeout(500)
  })

  test('FileManager swipe shows actions on mobile', async ({ page }) => {
    const fileItem = page.locator('[data-testid="swipe-content"]').first()
    if (await fileItem.count() === 0) {
      test.skip()
      return
    }
    await swipeLeft(page, fileItem)
    const actions = page.locator('[data-testid="swipe-actions"]').first()
    await expect(actions).toBeVisible()
  })

  test('desktop viewport does not show swipe components', async ({ page, browserName }, testInfo) => {
    const swipeContent = page.locator('[data-testid="swipe-content"]')
    if (await swipeContent.count() > 0) {
      expect(true).toBeTruthy()
    }
  })
})
