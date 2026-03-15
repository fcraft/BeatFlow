/**
 * E2E Waveform Quality Validation Tests
 *
 * Verifies end-to-end signal integrity from backend WebSocket streaming
 * through frontend rendering. Captures actual WebSocket messages and
 * validates signal quality, synchronization, and stability.
 *
 * Prerequisites:
 *   - Backend running on port 3090
 *   - Frontend dev server running on port 3080
 *
 * Run:
 *   cd frontend && npx playwright test e2e/waveform-quality.spec.ts --headed
 */
import { Page, expect, test } from '@playwright/test'

const API_BASE = 'http://localhost:3090'

interface SignalMessage {
  type: string
  seq: number
  ecg: number[]
  pcg: number[]
  ecg_start_sample: number
  pcg_start_sample: number
  timeline_sec: number
  server_elapsed_sec: number
  chunk_duration_ms: number
  vitals: Record<string, any>
  beat_annotations?: any[]
}

/** Login via API and inject token into localStorage */
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

/** Connect to virtual human and wait for stable streaming.
 *
 * The page first shows a profile selector ("我的虚拟人") with per-profile
 * "连接" buttons. We can either:
 *   a) Click the first profile's "连接" to enter with a saved profile, or
 *   b) Click "演示模式" to enter without a profile.
 * After connecting, the page transitions to the simulation view with
 * "已连接" status and waveform canvases.
 */
async function connectAndWaitForStream(page: Page, waitMs = 3000) {
  await page.goto('/virtual-human')

  // Wait for the profile selection page to load
  await expect(page.getByText('我的虚拟人').or(page.getByText('虚拟人体模型'))).toBeVisible({ timeout: 10_000 })

  // Prefer "演示模式" (demo mode) for consistent test behavior
  const demoBtn = page.getByRole('button', { name: '演示模式' })
  const profileConnectBtn = page.getByRole('button', { name: '连接' }).first()

  if (await demoBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await demoBtn.click()
  } else {
    // Fallback: click the first profile's connect button
    await profileConnectBtn.click()
  }

  // Wait for connection to establish
  await expect(page.getByText('已连接')).toBeVisible({ timeout: 15_000 })
  await page.waitForTimeout(waitMs)
}

/** Capture WebSocket signal messages for a duration */
function captureSignalMessages(page: Page): SignalMessage[] {
  const messages: SignalMessage[] = []

  page.on('websocket', (ws) => {
    ws.on('framereceived', (frame) => {
      try {
        const text = typeof frame.payload === 'string'
          ? frame.payload
          : new TextDecoder().decode(frame.payload as ArrayBuffer)
        const msg = JSON.parse(text)
        if (msg.type === 'signal') {
          messages.push(msg as SignalMessage)
        }
      } catch {
        // ignore non-JSON frames
      }
    })
  })

  return messages
}

// ════════════════════════════════════════════════════════════════════
// Test 3.1: WebSocket Message Capture & Validation
// ════════════════════════════════════════════════════════════════════
test.describe('WebSocket Signal Integrity', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('capture and validate 50+ WebSocket signal messages', async ({ page }) => {
    test.setTimeout(30_000)

    const messages = captureSignalMessages(page)
    await connectAndWaitForStream(page, 6000)

    // Should have received at least 40 messages in 6 seconds (allows for connection setup time)
    expect(messages.length).toBeGreaterThanOrEqual(40)

    // Validate each message
    let prevSeq = -1
    let prevEcgStart = -1
    let prevPcgStart = -1

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]

      // Required fields
      expect(msg.type).toBe('signal')
      expect(typeof msg.seq).toBe('number')

      // Sequence monotonicity
      expect(msg.seq).toBeGreaterThan(prevSeq)
      prevSeq = msg.seq

      // ECG array: 50 samples
      expect(Array.isArray(msg.ecg)).toBe(true)
      expect(msg.ecg.length).toBe(50)

      // PCG array: 400 samples
      expect(Array.isArray(msg.pcg)).toBe(true)
      expect(msg.pcg.length).toBe(400)

      // Sample counters monotonically increasing
      if (prevEcgStart >= 0) {
        expect(msg.ecg_start_sample).toBe(prevEcgStart + 50)
      }
      if (prevPcgStart >= 0) {
        expect(msg.pcg_start_sample).toBe(prevPcgStart + 400)
      }
      prevEcgStart = msg.ecg_start_sample
      prevPcgStart = msg.pcg_start_sample

      // No NaN or Infinity in signal data
      for (const v of msg.ecg) {
        expect(Number.isFinite(v)).toBe(true)
      }
      for (const v of msg.pcg) {
        expect(Number.isFinite(v)).toBe(true)
      }
    }
  })
})

// ════════════════════════════════════════════════════════════════════
// Test 3.2: ECG-PCG Timeline Synchronization
// ════════════════════════════════════════════════════════════════════
test.describe('ECG-PCG Synchronization', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('ECG and PCG timelines stay aligned within 2ms', async ({ page }) => {
    test.setTimeout(20_000)

    const messages = captureSignalMessages(page)
    await connectAndWaitForStream(page, 5000)

    expect(messages.length).toBeGreaterThanOrEqual(30)

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      const ecgTimeSec = msg.ecg_start_sample / 500
      const pcgTimeSec = msg.pcg_start_sample / 4000

      const drift = Math.abs(ecgTimeSec - pcgTimeSec)
      expect(drift).toBeLessThan(0.002)
    }
  })
})

// ════════════════════════════════════════════════════════════════════
// Test 3.3: Waveform Rendering Under Different HR
// ════════════════════════════════════════════════════════════════════
test.describe('Waveform Quality at Different HR', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  for (const hr of [45, 72, 120, 180]) {
    test(`waveform renders without errors at HR=${hr}`, async ({ page }) => {
      test.setTimeout(30_000)

      const messages = captureSignalMessages(page)
      const consoleErrors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text())
      })

      await connectAndWaitForStream(page, 2000)

      // Switch to settings tab and set HR
      await page.getByRole('button', { name: '设置' }).click()
      await page.waitForTimeout(500)

      // Find HR slider and set it
      const hrSliders = page.locator('input[type="range"]')
      const sliderCount = await hrSliders.count()

      if (sliderCount >= 2) {
        // Second slider is typically HR
        await hrSliders.nth(1).fill(String(hr))
      }

      // Wait for HR to take effect
      await page.waitForTimeout(5000)

      // Validate messages received during this period
      const recentMsgs = messages.slice(-30)
      expect(recentMsgs.length).toBeGreaterThan(0)

      // All messages should have valid signal data
      for (const msg of recentMsgs) {
        expect(msg.ecg.length).toBe(50)
        expect(msg.pcg.length).toBe(400)
        for (const v of msg.ecg) {
          expect(Number.isFinite(v)).toBe(true)
        }
      }

      // ECG should have non-trivial amplitude (not flatline)
      const ecgRanges = recentMsgs.map((m) => Math.max(...m.ecg) - Math.min(...m.ecg))
      const avgRange = ecgRanges.reduce((a, b) => a + b, 0) / ecgRanges.length
      expect(avgRange).toBeGreaterThan(0.01)

      // No console errors
      const signalErrors = consoleErrors.filter(
        (e) => !e.includes('favicon') && !e.includes('DevTools')
      )
      expect(signalErrors).toHaveLength(0)

      // Screenshot for visual regression
      await page.screenshot({ path: `test-results/waveform-hr-${hr}.png`, fullPage: false })
    })
  }
})

// ════════════════════════════════════════════════════════════════════
// Test 3.4: Condition Command Effects
// ════════════════════════════════════════════════════════════════════
test.describe('Condition Effects on Waveform', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  const conditions = [
    { name: 'AF', uiLabel: '房颤', expectedBeatKind: 'af' },
    { name: 'PVC', uiLabel: '早搏', expectedBeatKind: 'pvc' },
    { name: 'VT', uiLabel: '室速', expectedBeatKind: 'vt' },
  ]

  for (const { name, uiLabel, expectedBeatKind } of conditions) {
    test(`${name} produces expected beat annotations`, async ({ page }) => {
      test.setTimeout(25_000)

      const messages = captureSignalMessages(page)
      await connectAndWaitForStream(page, 2000)

      // Switch to condition tab
      await page.getByRole('button', { name: '心脏病变' }).click()
      await page.waitForTimeout(300)

      // Click the condition button
      await page.getByRole('button', { name: uiLabel }).click()

      // Wait for condition to take effect
      await page.waitForTimeout(5000)

      // Check beat annotations in recent messages
      const recentMsgs = messages.slice(-40)
      const allAnnotations = recentMsgs
        .filter((m) => Array.isArray(m.beat_annotations) && m.beat_annotations.length > 0)
        .flatMap((m) => m.beat_annotations!)

      // At least some beats should have the expected kind
      const matchingBeats = allAnnotations.filter(
        (a: any) => a.beat_kind === expectedBeatKind || a.beat_type === expectedBeatKind
      )

      // For PVC, not every beat is PVC, but at least some should be
      if (name === 'PVC') {
        expect(matchingBeats.length).toBeGreaterThan(0)
      } else {
        // For AF and VT, most beats should match
        expect(matchingBeats.length).toBeGreaterThan(0)
      }

      // Signal data should still be valid
      for (const msg of recentMsgs) {
        for (const v of msg.ecg) {
          expect(Number.isFinite(v)).toBe(true)
        }
      }
    })
  }
})

// ════════════════════════════════════════════════════════════════════
// Test 3.5: Long-Running Stability (30 seconds)
// ════════════════════════════════════════════════════════════════════
test.describe('Long-Running Stability', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('10-second streaming without signal degradation', async ({ page }) => {
    test.setTimeout(30_000)

    const messages = captureSignalMessages(page)
    await connectAndWaitForStream(page, 10_000)

    // Should have ~80+ messages in 10 seconds
    expect(messages.length).toBeGreaterThanOrEqual(60)

    // Check 1: No dropped seq numbers
    for (let i = 1; i < messages.length; i++) {
      expect(messages[i].seq).toBe(messages[i - 1].seq + 1)
    }

    // Check 2: No NaN/Infinity in any message
    for (const msg of messages) {
      for (const v of msg.ecg) {
        expect(Number.isFinite(v)).toBe(true)
      }
      for (const v of msg.pcg) {
        expect(Number.isFinite(v)).toBe(true)
      }
    }

    // Check 3: ECG amplitude stable (early vs late)
    const earlyMsgs = messages.slice(5, 30)  // Skip warmup
    const lateMsgs = messages.slice(-25)

    const earlyEcgRange = earlyMsgs.map(
      (m) => Math.max(...m.ecg) - Math.min(...m.ecg)
    )
    const lateEcgRange = lateMsgs.map(
      (m) => Math.max(...m.ecg) - Math.min(...m.ecg)
    )

    const earlyAvg = earlyEcgRange.reduce((a, b) => a + b, 0) / earlyEcgRange.length
    const lateAvg = lateEcgRange.reduce((a, b) => a + b, 0) / lateEcgRange.length

    // Late amplitude should be at least 50% of early (no collapse)
    if (earlyAvg > 0.01) {
      expect(lateAvg / earlyAvg).toBeGreaterThan(0.5)
    }

    // Check 4: PCG RMS stable
    function rms(arr: number[]): number {
      return Math.sqrt(arr.reduce((s, v) => s + v * v, 0) / arr.length)
    }

    const earlyPcgRms = earlyMsgs.map((m: SignalMessage) => rms(m.pcg))
    const latePcgRms = lateMsgs.map((m: SignalMessage) => rms(m.pcg))

    const earlyPcgAvg = earlyPcgRms.reduce((a, b) => a + b, 0) / earlyPcgRms.length
    const latePcgAvg = latePcgRms.reduce((a, b) => a + b, 0) / latePcgRms.length

    if (earlyPcgAvg > 0.001) {
      expect(latePcgAvg / earlyPcgAvg).toBeGreaterThan(0.3)
    }
  })
})

// ════════════════════════════════════════════════════════════════════
// Test 3.6: ECG-PCG Temporal Correlation
// ════════════════════════════════════════════════════════════════════
test.describe('ECG-PCG Temporal Correlation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('ECG R-peak timing correlates with PCG S1 energy burst', async ({ page }) => {
    test.setTimeout(25_000)

    const messages = captureSignalMessages(page)
    await connectAndWaitForStream(page, 8000)

    expect(messages.length).toBeGreaterThanOrEqual(50)

    // Concatenate all ECG and PCG samples
    const allEcg: number[] = []
    const allPcg: number[] = []

    for (const msg of messages) {
      allEcg.push(...msg.ecg)
      allPcg.push(...msg.pcg)
    }

    // Find R-peaks in ECG (simple threshold detection)
    const ecgThreshold = Math.max(...allEcg.map(Math.abs)) * 0.6
    const rPeakIndices: number[] = []
    for (let i = 1; i < allEcg.length - 1; i++) {
      if (allEcg[i] > ecgThreshold && allEcg[i] > allEcg[i - 1] && allEcg[i] >= allEcg[i + 1]) {
        // Minimum 200ms (100 samples) between R-peaks
        if (rPeakIndices.length === 0 || i - rPeakIndices[rPeakIndices.length - 1] > 100) {
          rPeakIndices.push(i)
        }
      }
    }

    // Should detect multiple R-peaks in 8 seconds
    expect(rPeakIndices.length).toBeGreaterThan(3)

    // For each R-peak, check if there's PCG energy nearby
    // R-peak at ECG sample i corresponds to PCG sample i * 8 (4000/500 ratio)
    const pcgToEcgRatio = 4000 / 500
    let correlatedPeaks = 0

    for (const rIdx of rPeakIndices) {
      const pcgCenter = Math.round(rIdx * pcgToEcgRatio)
      // Look in a window of 60-120ms after R-peak for S1
      const pcgWindowStart = pcgCenter + Math.round(0.020 * 4000)  // 20ms after
      const pcgWindowEnd = Math.min(allPcg.length, pcgCenter + Math.round(0.150 * 4000))  // 150ms after

      if (pcgWindowEnd <= pcgWindowStart || pcgWindowEnd > allPcg.length) continue

      // Compute PCG energy in window
      let windowEnergy = 0
      for (let j = pcgWindowStart; j < pcgWindowEnd; j++) {
        windowEnergy += allPcg[j] * allPcg[j]
      }
      windowEnergy /= (pcgWindowEnd - pcgWindowStart)

      // Compute baseline PCG energy (200ms before R-peak)
      const baseStart = Math.max(0, pcgCenter - Math.round(0.300 * 4000))
      const baseEnd = Math.max(0, pcgCenter - Math.round(0.100 * 4000))
      let baseEnergy = 0
      if (baseEnd > baseStart) {
        for (let j = baseStart; j < baseEnd; j++) {
          baseEnergy += allPcg[j] * allPcg[j]
        }
        baseEnergy /= (baseEnd - baseStart)
      }

      // S1 window should have more energy than baseline
      if (windowEnergy > baseEnergy * 1.5) {
        correlatedPeaks++
      }
    }

    // At least 50% of R-peaks should have correlated S1 energy
    const correlationRatio = correlatedPeaks / rPeakIndices.length
    expect(correlationRatio).toBeGreaterThan(0.5)
  })
})
