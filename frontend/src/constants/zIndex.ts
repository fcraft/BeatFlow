/**
 * 全局 z-index 管理器
 *
 * 每次调用 nextZIndex() 返回一个递增的 z-index 值，
 * 保证后打开的浮层永远在先打开的浮层之上。
 *
 * Toast 使用固定的极高值（不参与递增），始终在最顶层。
 */

let current = 9000

/** 获取下一个 z-index（递增，保证后创建的浮层在上） */
export function nextZIndex(): number {
  return ++current
}

/** Toast 固定层级，始终在最顶层 */
export const Z_TOAST = 99999
