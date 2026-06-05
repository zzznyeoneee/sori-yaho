'use client'

interface Instrument {
  id: string
  label: string
  icon: string
  available: boolean
}

const instruments: Instrument[] = [
  { id: 'piano', label: '피아노', icon: '🎹', available: true },
  { id: 'drums', label: '드럼', icon: '🥁', available: true },
  { id: 'guitar', label: '기타', icon: '🎸', available: false },
]

interface SidebarProps {
  selected: string
  onChange: (id: string) => void
}

export default function Sidebar({ selected, onChange }: SidebarProps) {
  return (
    <aside className="w-60 shrink-0 bg-[#16161d] border-r border-white/5 flex flex-col py-6 px-4 gap-2">
      <div className="px-2 mb-4">
        <h1 className="text-xl font-bold text-white tracking-tight">Sori-Yaho</h1>
        <p className="text-xs text-white/40 mt-1">음원 → 악보 자동 변환</p>
      </div>

      <p className="px-2 text-xs font-semibold text-white/30 uppercase tracking-widest mb-1">악기 선택</p>

      {instruments.map((inst) => (
        <button
          key={inst.id}
          disabled={!inst.available}
          onClick={() => inst.available && onChange(inst.id)}
          className={`
            flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
            ${!inst.available ? 'opacity-30 cursor-not-allowed text-white/50' : ''}
            ${inst.available && selected === inst.id
              ? 'bg-purple-600 text-white'
              : inst.available
                ? 'text-white/70 hover:bg-white/5 hover:text-white'
                : ''}
          `}
        >
          <span className="text-base">{inst.icon}</span>
          {inst.label}
          {!inst.available && (
            <span className="ml-auto text-[10px] bg-white/10 rounded px-1.5 py-0.5">준비 중</span>
          )}
        </button>
      ))}
    </aside>
  )
}
