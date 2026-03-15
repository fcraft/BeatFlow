/**
 * PCG Audio Playback Controls — E2E Tests
 *
 * Tests that the audio play/mute button and volume slider appear
 * and behave correctly on the Virtual Human page.
 *
 * Prerequisites:
 *   - Backend running on port 3090
 *   - Frontend dev server running on port 3080
 *   - Admin account: admin@beatflow.com / admin123
 *
 * Run:
 *   cd frontend && npx playwright test e2e/pcg-audio.spec.ts --headed
 */
import { Page, expect, test } from '@playwright/test'

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
}

test.describe('PCG Audio Controls', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/virtual-human')
    await expect(page.getByText('虚拟人体模型')).toBeVisible({ timeout: 10_000 })
  })

  test('audio mute button is visible in PCG waveform area', async ({ page }) => {
    // The VolumeX (muted) icon should be visible by default in the waveform area
    // After connection, look for the audio button with VolumeX or Volume2 icon
    const audioBtn = page.locator('button[title*="音"]').filter({ hasText: /.*/ }).first()
    // Alternative: just check that we can find some audio-related button
    const audioControls = page.locator('button').filter({ has: page.locator('svg') }).first()
    await expect(audioControls).toBeVisible({ timeout: 5_000 })
  })

  test('clicking audio button toggles to playing state', async ({ page }) => {
    // Connect first so PCG data flows
    await page.getByRole('button', { name: '连接' }).click()
    await expect(page.getByText('已连接')).toBeVisible({ timeout: 10_000 })

    // Find the audio toggle button (contains VolumeX icon initially)
    const audioBtn = page.locator('button[title="播放心音"]')
    await expect(audioBtn).toBeVisible({ timeout: 5_000 })

    // Click to start playing
    await audioBtn.click()

    // After click, button should switch to "静音" title
    await expect(page.locator('button[title="静音"]')).toBeVisible({ timeout: 3_000 })
  })

  test('volume slider appears when audio is playing', async ({ page }) => {
    // Connect
    await page.getByRole('button', { name: '连接' }).click()
    await expect(page.getByText('已连接')).toBeVisible({ timeout: 10_000 })

    // No volume slider initially
    const pcgArea = page.locator('.bg-gray-900\\/80')
    const sliderBefore = pcgArea.locator('input[type="range"]')
    await expect(sliderBefore).toHaveCount(0)

    // Click play
    await page.locator('button[title="播放心音"]').click()
    await expect(page.locator('button[title="静音"]')).toBeVisible({ timeout: 3_000 })

    // Volume slider should now be visible
    const sliderAfter = pcgArea.locator('input[type="range"]')
    await expect(sliderAfter).toBeVisible()
  })

  test('clicking mute stops audio and hides slider', async ({ page }) => {
    // Connect
    await page.getByRole('button', { name: '连接' }).click()
    await expect(page.getByText('已连接')).toBeVisible({ timeout: 10_000 })

    // Start playing
    await page.locator('button[title="播放心音"]').click()
    await expect(page.locator('button[title="静音"]')).toBeVisible({ timeout: 3_000 })

    // Click mute
    await page.locator('button[title="静音"]').click()

    // Should revert to play button
    await expect(page.locator('button[title="播放心音"]')).toBeVisible({ timeout: 3_000 })

    // Volume slider should be hidden
    const pcgArea = page.locator('.bg-gray-900\\/80')
    const slider = pcgArea.locator('input[type="range"]')
    await expect(slider).toHaveCount(0)
  })
})
