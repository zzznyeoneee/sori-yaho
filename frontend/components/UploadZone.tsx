'use client'

import { useRef, useState, DragEvent, ChangeEvent } from 'react'

interface UploadZoneProps {
  onFile: (file: File) => void
  disabled?: boolean
}

export default function UploadZone({ onFile, disabled }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && isAudio(file)) onFile(file)
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file && isAudio(file)) onFile(file)
    e.target.value = ''
  }

  function isAudio(file: File) {
    return file.type.startsWith('audio/') || /\.(mp3|wav|flac|m4a|ogg)$/i.test(file.name)
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`
        relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed
        p-12 cursor-pointer select-none transition-all
        ${disabled ? 'opacity-40 cursor-not-allowed' : ''}
        ${dragging
          ? 'border-purple-500 bg-purple-500/10'
          : 'border-white/10 bg-white/[0.03] hover:border-purple-600/50 hover:bg-white/[0.05]'}
      `}
    >
      <div className="text-5xl">{dragging ? '📂' : '🎵'}</div>
      <p className="text-white/80 font-medium text-sm text-center">
        MP3 또는 WAV 파일을 드래그하거나 클릭하세요
      </p>
      <p className="text-white/30 text-xs">최대 50MB · MP3, WAV, FLAC, M4A</p>
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.flac,.m4a"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  )
}
