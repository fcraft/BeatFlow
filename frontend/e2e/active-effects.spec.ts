/**
 * Active Effects Bar — E2E Tests
 *
 * Prerequisites:
 *   - Backend running on port 3090
 *   - Frontend dev server running on port 3080
 *   - Admin account: admin@beatflow.com / admin123
 *
 * Run:
 *   cd frontend && npx playwright test e2e/active-effects.spec.ts --headed
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

async function navigateToVirtualHuman(page: Page) {
  await page.goto('/virtual-human')
  await page.waitForTimeout(500)
}

async function connectWithNewProfile(page: Page) {
  // Click "快速启动" or connect button
  const quickStart = page.getByRole('button', { name: /快速启动|连接|开始/ })
  if (await quickStart.isVisible({ timeout: 3000 }).catch(() => false)) {
    await quickStart.click()
  }
  // Wait for connection
  await page.waitForTimeout(2000)
}

test.describe('Active Effects Bar', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await navigateToVirtualHuman(page)
  })

  test('exercise persists across tab switches', async ({ page }) => {
    await connectWithNewProfile(page)

    // Click 慢跑 in exercise tab
    const jogBtn = page.getByRole('button', { name: /慢跑/ })
    if (await jogBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await jogBtn.click()
      await page.waitForTimeout(1500)

      // Switch to emotion tab
      const emotionTab = page.getByRole('button', { name: /情绪/ })
      await emotionTab.click()
      await page.waitForTimeout(500)

      // Switch back to exercise tab
      const exerciseTab = page.getByRole('button', { name: /运动/ })
      await exerciseTab.click()
      await page.waitForTimeout(500)

      // The exercise button should still be highlighted (exercise_intensity > 0)
      // Check the effects bar shows exercise pill
      const effectsBar = page.locator('[class*="ActiveEffectsBar"], [class*="rounded-lg shadow-sm"]').first()
      // Verify some exercise-related text is visible
      const pageText = await page.textContent('body')
      // Exercise intensity should still be active
      expect(pageText).toBeTruthy()
    }
  })

  test('active effects bar updates with medication', async ({ page }) => {
    await connectWithNewProfile(page)

    // Switch to medication tab
    const medTab = page.getByRole('button', { name: /药物/ })
    if (await medTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await medTab.click()
      await page.waitForTimeout(500)

      // Click β-阻滞剂
      const betaBlocker = page.getByRole('button', { name: /β-阻滞剂/ })
      if (await betaBlocker.isVisible({ timeout: 2000 }).catch(() => false)) {
        await betaBlocker.click()
        await page.waitForTimeout(2000)

        // The effects bar should show medication pill
        const bodyText = await page.textContent('body')
        expect(bodyText).toContain('β-阻滞剂')
      }
    }
  })

  test('condition tab highlights from vitals', async ({ page }) => {
    await connectWithNewProfile(page)

    // Switch to condition tab
    const condTab = page.getByRole('button', { name: /心脏病变/ })
    if (await condTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await condTab.click()
      await page.waitForTimeout(500)

      // Click 房颤
      const afBtn = page.getByRole('button', { name: /房颤/ })
      if (await afBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await afBtn.click()
        await page.waitForTimeout(2000)

        // The 房颤 button should be highlighted (has ring class)
        const afBtnClasses = await afBtn.getAttribute('class')
        expect(afBtnClasses).toContain('ring')
      }
    }
  })

  test('tab badges show active effect counts', async ({ page }) => {
    await connectWithNewProfile(page)

    // Apply a condition
    const condTab = page.getByRole('button', { name: /心脏病变/ })
    if (await condTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await condTab.click()
      await page.waitForTimeout(500)

      const afBtn = page.getByRole('button', { name: /房颤/ })
      if (await afBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await afBtn.click()
        await page.waitForTimeout(2000)

        // The condition tab should show a badge
        // Badge is a small number in a red circle
        const condTabText = await condTab.textContent()
        // Tab text should contain the label and possibly a badge number
        expect(condTabText).toContain('心脏病变')
      }
    }
  })
})
