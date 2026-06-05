'use client'

import { useEffect, useRef, useState } from 'react'

interface MidiPlayerProps {
  url: string
  onMeasure?: (measure: number) => void
}

export default function MidiPlayer({ url, onMeasure }: MidiPlayerProps) {
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string>()

  const playerRef = useRef<any>(null)
  const instrumentRef = useRef<any>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const lastMeasureRef = useRef(-1)

  useEffect(() => {
    return () => {
      playerRef.current?.stop()
      audioCtxRef.current?.close()
    }
  }, [url])

  async function init() {
    if (playerRef.current) return true
    setLoading(true)
    setError(undefined)

    try {
      const MidiPlayer = (await import('midi-player-js' as any)) as any
      const Soundfont = (await import('soundfont-player' as any)) as any

      const PlayerClass = MidiPlayer?.default?.Player
        ?? MidiPlayer?.Player
        ?? MidiPlayer?.default
        ?? MidiPlayer

      const soundfont = Soundfont?.default ?? Soundfont

      audioCtxRef.current = new AudioContext()
      instrumentRef.current = await soundfont.instrument(
        audioCtxRef.current,
        'acoustic_grand_piano',
        { soundfont: 'FluidR3_GM' }
      )

      const player = new PlayerClass((event: any) => {
        if (!audioCtxRef.current || !instrumentRef.current) return

        if (event.name === 'Note on' && event.velocity > 0) {
          instrumentRef.current.play(
            event.noteName,
            audioCtxRef.current.currentTime,
            { gain: event.velocity / 127 }
          )
        }

        // 현재 마디 계산 (4/4 기준)
        const tick = player.getCurrentTick?.() ?? 0
        const ppq = player.division ?? 480
        const measure = Math.floor(tick / (ppq * 4))
        if (measure !== lastMeasureRef.current) {
          lastMeasureRef.current = measure
          onMeasure?.(measure)
        }

        const pct = player.getSongPercentRemaining?.()
        if (pct != null) setProgress(100 - pct)
      })

      player.on('endOfFile', () => {
        setPlaying(false)
        setProgress(0)
        lastMeasureRef.current = -1
        onMeasure?.(0)
      })

      const res = await fetch(url)
      const buf = await res.arrayBuffer()
      player.loadArrayBuffer(buf)

      playerRef.current = player
      return true
    } catch (e) {
      console.error(e)
      setError(e instanceof Error ? e.message : String(e))
      return false
    } finally {
      setLoading(false)
    }
  }

  async function togglePlay() {
    const ready = await init()
    if (!ready) return

    if (playing) {
      playerRef.current?.pause()
      setPlaying(false)
    } else {
      await audioCtxRef.current?.resume()
      playerRef.current?.play()
      setPlaying(true)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-4 bg-white/[0.03] rounded-xl px-4 py-3 border border-white/5">
        <button
          onClick={togglePlay}
          disabled={loading}
          className="w-9 h-9 rounded-full bg-purple-600 hover:bg-purple-500 disabled:opacity-50 flex items-center justify-center transition-colors shrink-0 text-sm"
        >
          {loading ? '…' : playing ? '⏸' : '▶'}
        </button>
        <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-600 transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      {error && <p className="text-xs text-red-400 px-1">재생 오류: {error}</p>}
    </div>
  )
}
