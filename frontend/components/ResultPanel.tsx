'use client'

import MidiPlayer from './MidiPlayer'
import SheetViewer from './SheetViewer'

export interface TranscribeResult {
  midiUrl: string
  musicxmlUrl: string
  instrument: string
  filename: string
}

interface ResultPanelProps {
  result: TranscribeResult
}

export default function ResultPanel({ result }: ResultPanelProps) {
  return (
    <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6 flex flex-col gap-6">
      <p className="text-sm font-semibold text-white/50 uppercase tracking-widest">결과</p>

      {/* MIDI 미리듣기 */}
      <div className="flex flex-col gap-3">
        <p className="text-xs text-white/40">MIDI 미리듣기</p>
        <MidiPlayer url={result.midiUrl} />
      </div>

      {/* 악보 미리보기 */}
      <div className="flex flex-col gap-3">
        <p className="text-xs text-white/40">악보 미리보기</p>
        <SheetViewer url={result.musicxmlUrl} />
      </div>

      {/* 다운로드 버튼 */}
      <div className="flex gap-3">
        <a
          href={result.midiUrl}
          download={`${result.filename}.mid`}
          className="flex-1 text-center py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-colors"
        >
          MIDI 다운로드
        </a>
        <a
          href={result.musicxmlUrl}
          download={`${result.filename}.musicxml`}
          className="flex-1 text-center py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white/80 text-sm font-semibold transition-colors"
        >
          MusicXML 다운로드
        </a>
      </div>
    </div>
  )
}
