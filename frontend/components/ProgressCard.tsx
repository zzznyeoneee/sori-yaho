'use client'

export type ProgressStep = 'idle' | 'uploading' | 'separating' | 'transcribing' | 'generating' | 'done' | 'error'

interface Step {
  id: ProgressStep
  label: string
}

const STEPS: Step[] = [
  { id: 'uploading', label: '파일 업로드' },
  { id: 'separating', label: '트랙 분리 (Demucs)' },
  { id: 'transcribing', label: '음표 감지' },
  { id: 'generating', label: 'MIDI / 악보 생성' },
  { id: 'done', label: '완료' },
]

const ORDER = STEPS.map((s) => s.id)

interface ProgressCardProps {
  step: ProgressStep
  errorMessage?: string
}

export default function ProgressCard({ step, errorMessage }: ProgressCardProps) {
  if (step === 'idle') return null

  const currentIndex = ORDER.indexOf(step as (typeof ORDER)[number])

  return (
    <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6">
      <p className="text-sm font-semibold text-white/50 uppercase tracking-widest mb-5">변환 진행 상태</p>

      <ol className="flex flex-col gap-3">
        {STEPS.map((s, i) => {
          const done = step !== 'error' && currentIndex > i
          const active = step !== 'error' && currentIndex === i
          const pending = step !== 'error' && currentIndex < i

          return (
            <li key={s.id} className="flex items-center gap-3">
              <span
                className={`
                  w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0
                  ${done ? 'bg-purple-600 text-white' : ''}
                  ${active ? 'bg-purple-600/30 border border-purple-500 text-purple-300 animate-pulse' : ''}
                  ${pending ? 'bg-white/5 border border-white/10 text-white/20' : ''}
                  ${step === 'error' ? 'bg-red-600/20 border border-red-500/30 text-red-400' : ''}
                `}
              >
                {done ? '✓' : i + 1}
              </span>
              <span
                className={`text-sm ${done || active ? 'text-white' : 'text-white/30'}`}
              >
                {s.label}
              </span>
              {active && step !== 'error' && (
                <span className="ml-auto text-xs text-purple-400 animate-pulse">처리 중…</span>
              )}
            </li>
          )
        })}
      </ol>

      {step === 'error' && (
        <div className="mt-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {errorMessage ?? '변환 중 오류가 발생했습니다. 다시 시도해 주세요.'}
        </div>
      )}
    </div>
  )
}
