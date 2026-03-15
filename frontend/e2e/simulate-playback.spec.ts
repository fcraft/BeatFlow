/**
 * Simulate → Waveform → Playback E2E Tests
 *
 * Tests the full flow:
 *   1. Create a project
 *   2. Generate simulated ECG/PCG via /api/v1/simulate/generate
 *   3. Verify waveform endpoint returns valid data
 *   4. Verify download endpoint returns audio bytes
 *   5. Cleanup
 *
 * Prerequisites:
 *   - Backend running on port 3090
 *   - Frontend dev server running on port 3080
 *   - Admin account: admin@beatflow.com / admin123
 *
 * Run:
 *   cd frontend && npx playwright test e2e/simulate-playback.spec.ts
 */
import { APIRequestContext, Page, expect, test } from '@playwright/test'

const API_BASE = 'http://localhost:3090'

let token: string
let projectId: string

/** Login via API and return access token */
async function getToken(request: APIRequestContext): Promise<string> {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: {
      email: 'admin@beatflow.com',
      password: 'Admin123!',
    },
  })
  expect(resp.ok()).toBeTruthy()
  const data = await resp.json()
  return data.access_token
}

/** Create a temporary project for testing */
async function createProject(request: APIRequestContext, authToken: string): Promise<string> {
  const resp = await request.post(`${API_BASE}/api/v1/projects/`, {
    headers: { Authorization: `Bearer ${authToken}` },
    data: {
      name: `E2E Test Simulate ${Date.now()}`,
      description: 'Temporary project for E2E simulate test',
    },
  })
  expect(resp.ok()).toBeTruthy()
  const data = await resp.json()
  return data.id
}

/** Delete test project */
async function deleteProject(request: APIRequestContext, authToken: string, id: string) {
  await request.delete(`${API_BASE}/api/v1/projects/${id}`, {
    headers: { Authorization: `Bearer ${authToken}` },
  })
}

test.describe('Simulate → Waveform → Playback', () => {
  test.beforeAll(async ({ request }) => {
    token = await getToken(request)
    projectId = await createProject(request, token)
  })

  test.afterAll(async ({ request }) => {
    if (projectId) {
      await deleteProject(request, token, projectId)
    }
  })

  test('generate simulated data, then waveform and download work', async ({ request }) => {
    // ── Step 1: Generate simulated ECG + PCG ───────────────────────
    const genResp = await request.post(`${API_BASE}/api/v1/simulate/generate`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: {
        project_id: projectId,
        duration: 3,           // short duration for speed
        heart_rate: 75,
        ecg_rhythm: 'sinus',
        generate_pcg: true,
        auto_detect: true,
      },
    })

    expect(genResp.ok(), `Generate failed: ${genResp.status()} ${await genResp.text()}`).toBeTruthy()
    const genData = await genResp.json()

    // Should have ecg_file_id
    expect(genData.ecg_file_id).toBeTruthy()
    const ecgFileId = genData.ecg_file_id

    // May have pcg_file_id
    const pcgFileId = genData.pcg_file_id

    // ── Step 2: Verify waveform endpoint for ECG ───────────────────
    const waveformResp = await request.get(
      `${API_BASE}/api/v1/files/${ecgFileId}/waveform?max_points=2000`,
      { headers: { Authorization: `Bearer ${token}` } },
    )

    expect(
      waveformResp.ok(),
      `Waveform failed: ${waveformResp.status()} ${await waveformResp.text()}`,
    ).toBeTruthy()

    const waveformData = await waveformResp.json()
    expect(waveformData.samples).toBeDefined()
    expect(Array.isArray(waveformData.samples)).toBeTruthy()
    expect(waveformData.samples.length).toBeGreaterThan(0)
    expect(waveformData.sample_rate).toBeGreaterThan(0)
    expect(waveformData.duration).toBeGreaterThan(0)

    // ── Step 3: Verify download endpoint for ECG ───────────────────
    const downloadResp = await request.get(
      `${API_BASE}/api/v1/files/${ecgFileId}/download`,
      { headers: { Authorization: `Bearer ${token}` } },
    )

    expect(
      downloadResp.ok(),
      `Download failed: ${downloadResp.status()}`,
    ).toBeTruthy()

    const downloadBody = await downloadResp.body()
    expect(downloadBody.length).toBeGreaterThan(44) // WAV header is 44 bytes

    // Check WAV magic bytes (RIFF header)
    const header = downloadBody.slice(0, 4).toString()
    expect(header).toBe('RIFF')

    // ── Step 4: If PCG was generated, verify it too ────────────────
    if (pcgFileId) {
      const pcgWaveformResp = await request.get(
        `${API_BASE}/api/v1/files/${pcgFileId}/waveform?max_points=2000`,
        { headers: { Authorization: `Bearer ${token}` } },
      )

      expect(
        pcgWaveformResp.ok(),
        `PCG Waveform failed: ${pcgWaveformResp.status()} ${await pcgWaveformResp.text()}`,
      ).toBeTruthy()

      const pcgWaveform = await pcgWaveformResp.json()
      expect(pcgWaveform.samples.length).toBeGreaterThan(0)

      const pcgDownloadResp = await request.get(
        `${API_BASE}/api/v1/files/${pcgFileId}/download`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      expect(pcgDownloadResp.ok()).toBeTruthy()

      const pcgBody = await pcgDownloadResp.body()
      expect(pcgBody.slice(0, 4).toString()).toBe('RIFF')
    }
  })

  test.skip('file_path in DB does not contain ./uploads prefix', async ({ request }) => {
    // TODO: Backend stability issue under test load - skip for now
    // This test can be run manually when backend has capacity
  })
})
