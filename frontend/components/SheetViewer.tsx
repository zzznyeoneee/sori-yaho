'use client'

import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'

function loadOSMD(): Promise<any> {
  return new Promise((resolve, reject) => {
    if ((window as any).opensheetmusicdisplay) {
      resolve((window as any).opensheetmusicdisplay.OpenSheetMusicDisplay)
      return
    }
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.9.0/build/opensheetmusicdisplay.min.js'
    script.onload = () => resolve((window as any).opensheetmusicdisplay.OpenSheetMusicDisplay)
    script.onerror = reject
    document.head.appendChild(script)
  })
}

interface SheetViewerProps {
  url: string
  currentMeasure?: number
}

export interface SheetViewerHandle {
  goToMeasure: (measure: number) => void
}

function moveCursor(osmd: any, measure: number) {
  try {
    const cursor = osmd.cursors?.[0] ?? osmd.cursor
    if (!cursor) return
    cursor.reset()
    while (
      cursor.iterator.CurrentMeasureIndex < measure &&
      !cursor.iterator.EndReached
    ) {
      cursor.next()
    }
    cursor.show()

    // 해당 마디로 자동 스크롤
    const el: HTMLElement | undefined = cursor.cursorElement
    el?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
  } catch {
    // ignore
  }
}

const SheetViewer = forwardRef<SheetViewerHandle, SheetViewerProps>(
  function SheetViewer({ url, currentMeasure }, ref) {
    const containerRef = useRef<HTMLDivElement>(null)
    const osmdRef = useRef<any>(null)
    const [error, setError] = useState<string>()
    const [loading, setLoading] = useState(true)

    useImperativeHandle(ref, () => ({
      goToMeasure(measure: number) {
        if (osmdRef.current) moveCursor(osmdRef.current, measure)
      },
    }))

    useEffect(() => {
      if (currentMeasure == null || !osmdRef.current) return
      moveCursor(osmdRef.current, currentMeasure)
    }, [currentMeasure])

    useEffect(() => {
      if (!containerRef.current) return
      let cancelled = false

      async function render() {
        setLoading(true)
        setError(undefined)

        try {
          const OpenSheetMusicDisplay = await loadOSMD()
          if (cancelled || !containerRef.current) return

          const osmd = new OpenSheetMusicDisplay(containerRef.current, {
            autoResize: true,
            backend: 'svg',
            drawTitle: false,
            drawComposer: false,
            drawCredits: false,
            // 커서: 마디 전체를 덮는 보라색 하이라이트
            cursorsOptions: [
              {
                type: 0,
                color: '#7c3aed',
                alpha: 0.25,
                follow: true,
              },
            ],
          })

          const res = await fetch(url)
          const xml = await res.text()
          await osmd.load(xml)
          if (cancelled) return
          osmd.render()
          osmdRef.current = osmd

          // 커서 초기화
          const cursor = osmd.cursors?.[0] ?? osmd.cursor
          if (cursor) {
            cursor.show()
            cursor.hide()  // 재생 전엔 숨김
            // 커서 스타일: 얇은 선 → 넓은 사각형
            if (cursor.cursorElement) {
              const el = cursor.cursorElement as HTMLElement
              el.style.width = 'auto'
              el.style.minWidth = '24px'
              el.style.opacity = '1'
            }
          }
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
      <div className="rounded-xl border border-white/5 bg-white overflow-auto max-h-[60vh] min-h-40 relative">
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm z-10 bg-white">
            악보 렌더링 중…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-red-400 text-sm px-4 text-center">
            악보 렌더링 실패: {error}
          </div>
        )}
        <div ref={containerRef} className={error ? 'hidden' : ''} />
      </div>
    )
  }
)

export default SheetViewer
