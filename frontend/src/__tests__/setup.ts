/**
 * Vitest global setup — mock Web Audio API for jsdom
 *
 * 提供两套 mock：
 *   - MockAudioContext（默认）：audioWorklet 可用
 *   - MockAudioContextNoWorklet：audioWorklet 为 undefined（模拟非安全上下文）
 *
 * 测试可通过替换 globalThis.AudioContext 来切换场景。
 */

// ── 共用工具 ──
function createMockGain() {
  return {
    gain: { value: 1, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
    connect: vi.fn(),
    disconnect: vi.fn(),
  }
}

function createMockScriptProcessor() {
  return {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onaudioprocess: null as any,
  }
}

function createMockBiquadFilter() {
  return {
    type: 'lowpass',
    frequency: { value: 350, linearRampToValueAtTime: vi.fn() },
    Q: { value: 1, linearRampToValueAtTime: vi.fn() },
    gain: { value: 0, linearRampToValueAtTime: vi.fn() },
    connect: vi.fn(),
    disconnect: vi.fn(),
  }
}

// ── 带 AudioWorklet 的 AudioContext ──
class MockAudioContext {
  sampleRate = 44100
  state = 'running' as AudioContextState
  currentTime = 0
  destination = {}

  async resume() { this.state = 'running' }
  async close() { this.state = 'closed' }
  createGain(): any { return createMockGain() }
  createScriptProcessor(): any { return createMockScriptProcessor() }
  createBiquadFilter(): any { return createMockBiquadFilter() }

  get audioWorklet(): any {
    return { addModule: vi.fn().mockResolvedValue(undefined) }
  }
}

// ── 不带 AudioWorklet 的 AudioContext（模拟非安全上下文） ──
class MockAudioContextNoWorklet {
  sampleRate = 44100
  state = 'running' as AudioContextState
  currentTime = 0
  destination = {}

  async resume() { this.state = 'running' }
  async close() { this.state = 'closed' }
  createGain(): any { return createMockGain() }
  createScriptProcessor(): any { return createMockScriptProcessor() }
  createBiquadFilter(): any { return createMockBiquadFilter() }

  get audioWorklet(): undefined { return undefined }
}

// ── AudioWorkletNode mock ──
class MockAudioWorkletNode {
  port = {
    postMessage: vi.fn(),
    onmessage: null as any,
  }
  connect = vi.fn()
  disconnect = vi.fn()
  constructor(_ctx: any, _name: string) {}
}

// ── Install defaults ──
if (typeof globalThis.AudioContext === 'undefined') {
  (globalThis as any).AudioContext = MockAudioContext
}
if (typeof globalThis.AudioWorkletNode === 'undefined') {
  (globalThis as any).AudioWorkletNode = MockAudioWorkletNode
}

// ── Export for tests to swap ──
export { MockAudioContext, MockAudioContextNoWorklet, MockAudioWorkletNode }
