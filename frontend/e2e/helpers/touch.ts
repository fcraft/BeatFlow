import type { Page, Locator } from '@playwright/test'

/**
 * Simulate a left swipe on a target element.
 */
export async function swipeLeft(page: Page, target: Locator, distance = 120): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for swipe')

  const startX = box.x + box.width * 0.8
  const startY = box.y + box.height / 2
  const endX = startX - distance

  await page.touchscreen.tap(startX, startY)
  await page.evaluate(
    ({ sx, sy, ex, ey }) => {
      const el = document.elementFromPoint(sx, sy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: sy })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchmove', {
        touches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
    },
    { sx: startX, sy: startY, ex: endX, ey: startY }
  )
  await page.waitForTimeout(350)
}

/**
 * Simulate a right swipe on a target element.
 */
export async function swipeRight(page: Page, target: Locator, distance = 120): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for swipe')

  const startX = box.x + box.width * 0.2
  const startY = box.y + box.height / 2
  const endX = startX + distance

  await page.evaluate(
    ({ sx, sy, ex, ey }) => {
      const el = document.elementFromPoint(sx, sy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: sy })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchmove', {
        touches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
    },
    { sx: startX, sy: startY, ex: endX, ey: startY }
  )
  await page.waitForTimeout(350)
}

/**
 * Simulate a long press on a target element.
 */
export async function longPress(page: Page, target: Locator, duration = 600): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for long press')

  const x = box.x + box.width / 2
  const y = box.y + box.height / 2

  await page.evaluate(
    ({ cx, cy }) => {
      const el = document.elementFromPoint(cx, cy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: cx, clientY: cy })],
        bubbles: true,
      }))
    },
    { cx: x, cy: y }
  )
  await page.waitForTimeout(duration)
  await page.evaluate(
    ({ cx, cy }) => {
      const el = document.elementFromPoint(cx, cy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: cx, clientY: cy })],
        bubbles: true,
      }))
    },
    { cx: x, cy: y }
  )
  await page.waitForTimeout(200)
}

/**
 * Simulate a downward swipe (for BottomSheet dismiss).
 */
export async function swipeDown(page: Page, target: Locator, distance = 200): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for swipe down')

  const startX = box.x + box.width / 2
  const startY = box.y + 20
  const endY = startY + distance

  await page.evaluate(
    ({ sx, sy, ey }) => {
      const el = document.elementFromPoint(sx, sy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: sy })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchmove', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: ey })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: ey })],
        bubbles: true,
      }))
    },
    { sx: startX, sy: startY, ey: endY }
  )
  await page.waitForTimeout(350)
}
