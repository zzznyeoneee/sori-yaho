'use client'

import { useState } from 'react'
import Sidebar from '@/components/Sidebar'
import UploadZone from '@/components/UploadZone'
import ProgressCard, { ProgressStep } from '@/components/ProgressCard'
import ResultPanel, { TranscribeResult } from '@/components/ResultPanel'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function Home() {
  const [instrument, setInstrument] = useState('drums')
  const [step, setStep] = useState<ProgressStep>('idle')
  const [errorMessage, setErrorMessage] = useState<string>()
  const [result, setResult] = useState<TranscribeResult | null>(null)

  async function handleFile(file: File) {
    setResult(null)
    setErrorMessage(undefined)
    setStep('uploading')

    const form = new FormData()
    form.append('file', file)
    form.append('instrument', instrument)

    try {
      setStep('separating')
      const res = await fetch(`${API_BASE}/api/transcribe`, {
        method: 'POST',
        body: form,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail ?? `서버 오류 (${res.status})`)
      }

      setStep('generating')
      const data = await res.json()
      setResult({
        midiUrl: `${API_BASE}${data.midi_url}`,
        musicxmlUrl: `${API_BASE}${data.musicxml_url}`,
        instrument: data.instrument,
        filename: file.name.replace(/\.[^.]+$/, ''),
      })
      setStep('done')
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : String(e))
      setStep('error')
    }
  }

  const busy = step !== 'idle' && step !== 'done' && step !== 'error'

  return (
    <div className="flex min-h-screen bg-[#0f0f13] text-white">
      <Sidebar
        selected={instrument}
        onChange={(id) => { setInstrument(id); setStep('idle'); setResult(null) }}
        onHome={() => { setStep('idle'); setResult(null) }}
      />

      <main className="flex-1 flex gap-6 p-8 min-w-0">
        {/* 왼쪽: 업로드 + 진행 상태 */}
        <div className="flex flex-col gap-6 w-96 shrink-0">
          <div>
            <h2 className="text-2xl font-bold">음원 채보</h2>
            <p className="text-white/40 text-sm mt-1">MP3 또는 WAV를 업로드하면 MIDI와 악보로 변환합니다.</p>
          </div>

          <UploadZone onFile={handleFile} disabled={busy} />

          {step !== 'idle' && <ProgressCard step={step} errorMessage={errorMessage} />}
        </div>

        {/* 오른쪽: 결과 */}
        {result && step === 'done' && (
          <div className="flex-1 min-w-0">
            <ResultPanel result={result} />
          </div>
        )}
      </main>
    </div>
  )
}
