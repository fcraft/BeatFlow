import { test, expect } from '@playwright/test'
import { swipeLeft, swipeRight, longPress } from '../helpers/touch'

const API_BASE = 'http://localhost:3090'

async function login(page, request) {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { username: 'admin', password: 'Admin123!' },
  })
  const { access_token } = await resp.json()
  await page.goto('/')
  await page.evaluate((token) => localStorage.setItem('token', token), access_token)
  return access_token
}

test.describe('ProjectListView — Mobile', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('mobile'), 'Desktop-only skip')

  test.beforeEach(async ({ page, request }) => {
    await login(page, request)
    await page.goto('/projects')
    await page.waitForLoadState('networkidle')
  })

  test('shows single-column grid on mobile', async ({ page }) => {
    const grid = page.locator('.grid')
    await expect(grid).toBeVisible()
    const cols = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(cols.split(' ').length).toBe(1)
  })

  test('FAB button is visible', async ({ page }) => {
    const fab = page.locator('[data-testid="fab"]')
    await expect(fab).toBeVisible()
  })

  test('FAB opens create modal as bottom sheet', async ({ page }) => {
    await page.locator('[data-testid="fab"]').click()
    await expect(page.locator('text=新建项目').first()).toBeVisible()
    await expect(page.locator('text=项目名称').first()).toBeVisible()
  })

  test('swipe left reveals action buttons', async ({ page }) => {
    const firstCard = page.locator('[data-testid="swipe-content"]').first()
    if (await firstCard.count() === 0) {
      test.skip()
      return
    }
    await swipeLeft(page, firstCard)
    const actions = page.locator('[data-testid="swipe-actions"]').first()
    await expect(actions).toBeVisible()
  })

  test('long press shows context menu', async ({ page }) => {
    const firstCard = page.locator('.card-hover').first()
    if (await firstCard.count() === 0) {
      test.skip()
      return
    }
    await longPress(page, firstCard)
    const menu = page.locator('[data-testid="long-press-menu"]')
    await expect(menu).toBeVisible()
    await expect(page.locator('text=查看详情')).toBeVisible()
    await expect(page.locator('text=编辑')).toBeVisible()
    await expect(page.locator('text=删除')).toBeVisible()
  })
})

test.describe('ProjectListView — Tablet', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('tablet'), 'Mobile/Desktop skip')

  test.beforeEach(async ({ page, request }) => {
    await login(page, request)
    await page.goto('/projects')
    await page.waitForLoadState('networkidle')
  })

  test('shows two-column grid on tablet', async ({ page }) => {
    const grid = page.locator('.grid')
    await expect(grid).toBeVisible()
    const cols = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(cols.split(' ').length).toBe(2)
  })
})
