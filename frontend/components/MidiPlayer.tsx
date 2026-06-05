'use client'

import { useEffect, useRef, useState } from 'react'

interface MidiPlayerProps {
  url: string
}

export default function MidiPlayer({ url }: MidiPlayerProps) {
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string>()

  const playerRef = useRef<any>(null)
  const soundfontRef = useRef<any>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const activeNodesRef = useRef<AudioBufferSourceNode[]>([])

  useEffect(() => {
    return () => {
      playerRef.current?.stop()
      audioCtxRef.current?.close()
    }
  }, [])

  async function init() {
    if (playerRef.current) return true

    setLoading(true)
    setError(undefined)

    try {
      const [{ default: MidiPlayer }, Soundfont] = await Promise.all([
        import('midi-player-js'),
        import('soundfont-player'),
      ])

      audioCtxRef.current = new AudioContext()
      const instrument = await Soundfont.instrument(audioCtxRef.current, 'acoustic_grand_piano')
      soundfontRef.current = instrument

      const player = new MidiPlayer.Player((event: any) => {
        if (event.name === 'Note on' && event.velocity > 0) {
          soundfontRef.current?.play(event.noteName, audioCtxRef.current!.currentTime, {
            gain: event.velocity / 100,
          })
        }
        if (player.getSongPercentRemaining !== undefined) {
          setProgress(100 - player.getSongPercentRemaining())
        }
      })

      player.on('endOfFile', () => {
        setPlaying(false)
        setProgress(0)
      })

      const res = await fetch(url)
      const buf = await res.arrayBuffer()
      player.loadArrayBuffer(buf)

      playerRef.current = player
      return true
    } catch (e) {
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
      audioCtxRef.current?.resume()
      playerRef.current?.play()
      setPlaying(true)
    }
  }

  return (
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
          className="h-full bg-purple-600 transition-all duration-200"
          style={{ width: `${progress}%` }}
        />
      </div>

      {error && <span className="text-xs text-red-400 ml-2">{error}</span>}
    </div>
  )
}
