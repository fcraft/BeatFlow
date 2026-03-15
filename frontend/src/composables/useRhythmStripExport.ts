/**
 * useRhythmStripExport
 * Utilities for exporting the ECG rhythm strip canvas as a PNG with vitals header.
 */

const RHYTHM_LABELS: Record<string, string> = {
  normal: '窦性',
  af: '房颤',
  pvc: '早搏',
  vt: 'VT',
  svt: 'SVT',
  vf: 'VF',
  asystole: '停搏',
}

/**
 * Generate a filename for the exported rhythm strip.
 * Format: ECG_{rhythm}_{lead}_{YYYYMMDD}_{HHmmss}.{ext}
 */
export function generateFilename(rhythm: string, lead: string, ext: string): string {
  const now = new Date()
  const pad = (n: number, len = 2) => String(n).padStart(len, '0')
  const date =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
  const time =
    `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  return `ECG_${rhythm}_${lead}_${date}_${time}.${ext}`
}

/**
 * Format a vitals header string for the exported image.
 * Returns: "HR: {hr} bpm | 节律: {rhythmLabel}"
 */
export function formatVitalsHeader(vitals: Record<string, any>): string {
  const hr = vitals.heart_rate ?? 0
  const rhythmKey = vitals.rhythm ?? ''
  const rhythmLabel = RHYTHM_LABELS[rhythmKey] ?? rhythmKey
  return `HR: ${hr} bpm | 节律: ${rhythmLabel}`
}

/**
 * Export the ECG canvas as a PNG with a vitals header drawn on top.
 * Creates a new canvas with an extra 40px header band, then triggers download.
 */
export function exportCanvasAsPng(
  sourceCanvas: HTMLCanvasElement,
  vitals: Record<string, any>,
  lead: string,
): void {
  const HEADER_HEIGHT = 40
  const width = sourceCanvas.width
  const height = sourceCanvas.height

  const offscreen = document.createElement('canvas')
  offscreen.width = width
  offscreen.height = height + HEADER_HEIGHT

  const ctx = offscreen.getContext('2d')
  if (!ctx) return

  // Dark background
  ctx.fillStyle = '#111827'
  ctx.fillRect(0, 0, width, height + HEADER_HEIGHT)

  // Draw header text
  ctx.fillStyle = '#9ca3af'
  ctx.font = '12px monospace'
  ctx.textBaseline = 'middle'

  const vitalsLine = formatVitalsHeader(vitals)
  const calLine = `Lead ${lead} | 25mm/s | 10mm/mV`

  ctx.fillText(vitalsLine, 8, 12)
  ctx.fillText(calLine, 8, 28)

  // Copy source canvas below header
  ctx.drawImage(sourceCanvas, 0, HEADER_HEIGHT)

  // Trigger download
  offscreen.toBlob((blob) => {
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = generateFilename(vitals.rhythm ?? 'ecg', lead, 'png')
    a.click()
    URL.revokeObjectURL(url)
  }, 'image/png')
}
