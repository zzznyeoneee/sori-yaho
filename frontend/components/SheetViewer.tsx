'use client'

import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'

interface SheetViewerProps {
  url: string
  currentMeasure?: number
}

export interface SheetViewerHandle {
  goToMeasure: (measure: number) => void
}

const SheetViewer = forwardRef<SheetViewerHandle, SheetViewerProps>(
  function SheetViewer({ url, currentMeasure }, ref) {
    const containerRef = useRef<HTMLDivElement>(null)
    const osmdRef = useRef<any>(null)
    const [error, setError] = useState<string>()
    const [loading, setLoading] = useState(true)

    useImperativeHandle(ref, () => ({
      goToMeasure(measure: number) {
        const osmd = osmdRef.current
        if (!osmd?.cursor) return
        try {
          osmd.cursor.reset()
          while (
            osmd.cursor.iterator.CurrentMeasureIndex < measure &&
            !osmd.cursor.iterator.EndReached
          ) {
            osmd.cursor.next()
          }
          osmd.cursor.show()
        } catch {
          // cursor 이동 실패 시 무시
        }
      },
    }))

    // currentMeasure prop 변경 시 cursor 이동
    useEffect(() => {
      if (currentMeasure == null) return
      const osmd = osmdRef.current
      if (!osmd?.cursor) return
      try {
        osmd.cursor.reset()
        while (
          osmd.cursor.iterator.CurrentMeasureIndex < currentMeasure &&
          !osmd.cursor.iterator.EndReached
        ) {
          osmd.cursor.next()
        }
        osmd.cursor.show()
      } catch {
        // ignore
      }
    }, [currentMeasure])

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
          osmdRef.current = osmd
        } catch (e) {
          console.error('SheetViewer error:', e)
          if (!cancelled) setError(e instanceof Error ? e.message : String(e))
        } finally {
          if (!cancelled) setLoading(false)
        }
      }

      render()
      return () => { cancelled = true; osmdRef.current = null }
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
)

export default SheetViewer
