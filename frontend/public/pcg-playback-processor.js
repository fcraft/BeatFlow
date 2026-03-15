/**
 * PCG AudioWorklet Processor
 *
 * Runs on the audio rendering thread. Receives upsampled PCG samples
 * via MessagePort and outputs them to the speaker in 128-sample frames.
 */
class PcgPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    /** @type {Float32Array[]} - queue of sample chunks */
    this._queue = []
    /** Total samples buffered across all queued chunks */
    this._queued = 0
    /** Read offset within the first chunk in queue */
    this._readOffset = 0

    this.port.onmessage = (e) => {
      if (e.data.type === 'samples') {
        // e.data.samples is a Float32Array (transferred, zero-copy)
        this._queue.push(e.data.samples)
        this._queued += e.data.samples.length
      } else if (e.data.type === 'clear') {
        this._queue.length = 0
        this._queued = 0
        this._readOffset = 0
      }
    }
  }

  process(_inputs, outputs) {
    const output = outputs[0]
    if (!output || !output[0]) return true

    const channel = output[0] // mono
    const needed = channel.length // typically 128

    let written = 0
    while (written < needed && this._queue.length > 0) {
      const chunk = this._queue[0]
      const available = chunk.length - this._readOffset
      const toCopy = Math.min(available, needed - written)

      channel.set(
        chunk.subarray(this._readOffset, this._readOffset + toCopy),
        written,
      )

      written += toCopy
      this._readOffset += toCopy
      this._queued -= toCopy

      if (this._readOffset >= chunk.length) {
        this._queue.shift()
        this._readOffset = 0
      }
    }

    // Fill remaining with silence if buffer underrun
    if (written < needed) {
      channel.fill(0, written)
    }

    return true // keep processor alive
  }
}

registerProcessor('pcg-playback-processor', PcgPlaybackProcessor)
