'use client'

import { useEffect, useRef, useState } from 'react'

interface SheetViewerProps {
  url: string
}

export default function SheetViewer({ url }: SheetViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!containerRef.current) return

    let cancelled = false

    async function render() {
      setLoading(true)
      setError(undefined)

      try {
        const { OpenSheetMusicDisplay } = await import('opensheetmusicdisplay')
        if (cancelled || !containerRef.current) return

        const osmd = new OpenSheetMusicDisplay(containerRef.current, {
          autoResize: true,
          backend: 'svg',
          drawTitle: false,
          drawComposer: false,
          drawCredits: false,
        })

        const res = await fetch(url)
        const xml = await res.text()
        await osmd.load(xml)
        if (cancelled) return
        osmd.render()
      } catch (e) {
        console.error('SheetViewer error:', e)
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    render()
    return () => { cancelled = true }
  }, [url])

  return (
    <div className="rounded-xl border border-white/5 bg-white overflow-auto max-h-[60vh] min-h-40">
      {loading && !error && (
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
          악보 렌더링 중…
        </div>
      )}
      {error && (
        <div className="flex items-center justify-center h-40 text-red-400 text-sm px-4 text-center">
          악보 렌더링 실패: {error}
        </div>
      )}
      <div ref={containerRef} className={loading || error ? 'hidden' : ''} />
    </div>
  )
}
