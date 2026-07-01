'use client'

import { useEffect, useRef, useState } from 'react'

// GM drum note → soundfont instrument name
const DRUM_INSTRUMENT_MAP: Record<number, string> = {
  36: 'taiko_drum',
  37: 'taiko_drum',
  38: 'synth_drum',
  39: 'synth_drum',
  40: 'synth_drum',
  41: 'woodblock',
  42: 'woodblock',
  43: 'woodblock',
  44: 'woodblock',
  45: 'woodblock',
  46: 'woodblock',
  47: 'woodblock',
  48: 'woodblock',
  49: 'taiko_drum',
  50: 'woodblock',
  51: 'woodblock',
}

interface MidiPlayerProps {
  url: string
  instrument?: string
  onMeasure?: (measure: number) => void
}

export default function MidiPlayer({ url, instrument, onMeasure }: MidiPlayerProps) {
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentMeasure, setCurrentMeasure] = useState(0)
  const [totalMeasures, setTotalMeasures] = useState(0)
  const [error, setError] = useState<string>()

  const playerRef = useRef<any>(null)
  const instrumentRef = useRef<any>(null)
  const drumInstrumentsRef = useRef<Record<string, any>>({})
  const audioCtxRef = useRef<AudioContext | null>(null)
  const lastMeasureRef = useRef(-1)
  const isDrums = instrument === 'drums'
  const isBass = instrument === 'bass'
  const isVocal = instrument === 'vocal'

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
      const ctx = audioCtxRef.current

      if (isDrums) {
        const needed = [...new Set(Object.values(DRUM_INSTRUMENT_MAP))]
        const loaded = await Promise.all(
          needed.map(name =>
            soundfont.instrument(ctx, name, { soundfont: 'FluidR3_GM' })
              .then((inst: any) => [name, inst] as const)
          )
        )
        drumInstrumentsRef.current = Object.fromEntries(loaded)
      } else {
        const soundfontName = isBass ? 'electric_bass_finger' : isVocal ? 'choir_aahs' : 'acoustic_grand_piano'
        instrumentRef.current = await soundfont.instrument(
          ctx, soundfontName, { soundfont: 'FluidR3_GM' }
        )
      }

      const player = new PlayerClass((event: any) => {
        if (!audioCtxRef.current) return

        if (event.name === 'Note on' && event.velocity > 0) {
          const gain = event.velocity / 127
          if (isDrums) {
            const midiNote: number = event.noteNumber ?? 60
            const instName = DRUM_INSTRUMENT_MAP[midiNote] ?? 'synth_drum'
            drumInstrumentsRef.current[instName]?.play(
              event.noteName, audioCtxRef.current.currentTime, { gain }
            )
          } else {
            instrumentRef.current?.play(
              event.noteName, audioCtxRef.current.currentTime, { gain }
            )
          }
        }

        // 진행도
        const pct = player.getSongPercentRemaining?.()
        if (pct != null) setProgress(100 - pct)

        // 현재 마디
        const tick = player.getCurrentTick?.() ?? 0
        const ppq = player.division ?? 480
        const measure = Math.floor(tick / (ppq * 4))
        if (measure !== lastMeasureRef.current) {
          lastMeasureRef.current = measure
          setCurrentMeasure(measure + 1)
          onMeasure?.(measure)
        }
      })

      player.on('endOfFile', () => {
        setPlaying(false)
        setProgress(0)
        setCurrentMeasure(0)
        lastMeasureRef.current = -1
        onMeasure?.(0)
      })

      const res = await fetch(url)
      const buf = await res.arrayBuffer()
      player.loadArrayBuffer(buf)

      // 총 마디 수 계산
      const totalTicks = player.getTotalTicks?.() ?? 0
      const ppq = player.division ?? 480
      setTotalMeasures(Math.max(1, Math.ceil(totalTicks / (ppq * 4))))

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

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const pct = Number(e.target.value)
    setProgress(pct)
    const player = playerRef.current
    if (!player) return

    const total = player.getTotalTicks?.() ?? 0
    const tick = Math.floor((pct / 100) * total)
    player.skipToTick?.(tick)

    const ppq = player.division ?? 480
    const measure = Math.floor(tick / (ppq * 4))
    lastMeasureRef.current = measure
    setCurrentMeasure(measure + 1)
    onMeasure?.(measure)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3 bg-white/[0.03] rounded-xl px-4 py-3 border border-white/5">
        <button
          onClick={togglePlay}
          disabled={loading}
          className="w-9 h-9 rounded-full bg-purple-600 hover:bg-purple-500 disabled:opacity-50 flex items-center justify-center transition-colors shrink-0 text-sm"
        >
          {loading ? '…' : playing ? '⏸' : '▶'}
        </button>

        {/* seekbar */}
        <div className="flex-1 relative flex items-center">
          <div className="absolute inset-y-0 left-0 right-0 flex items-center pointer-events-none">
            <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-600"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={0.1}
            value={progress}
            onChange={handleSeek}
            className="relative w-full h-1 appearance-none bg-transparent cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow"
          />
        </div>

        {/* 마디 표시 */}
        <span className="text-xs text-white/50 shrink-0 w-16 text-right tabular-nums">
          {currentMeasure > 0
            ? `${currentMeasure} / ${totalMeasures || '?'} 마디`
            : totalMeasures > 0 ? `${totalMeasures} 마디` : ''}
        </span>
      </div>
      {error && <p className="text-xs text-red-400 px-1">재생 오류: {error}</p>}
    </div>
  )
}
