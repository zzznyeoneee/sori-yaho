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

function highlightMeasure(osmd: any, measureIndex: number) {
  try {
    const container = osmd.container as HTMLElement | undefined
    if (!container) return
    const svg = container.querySelector('svg')
    if (!svg) return

    // 이전 하이라이트 제거
    svg.querySelectorAll('.sori-highlight').forEach((el: Element) => el.remove())
    if (measureIndex < 0) return

    const measureList: any[][] =
      osmd.GraphicSheet?.MeasureList ?? osmd.graphic?.MeasureList
    if (!measureList || measureIndex >= measureList.length) return

    const staffMeasures: any[] = measureList[measureIndex] ?? []
    for (const m of staffMeasures) {
      if (!m?.PositionAndShape) continue
      const pos = m.PositionAndShape.AbsolutePosition
      const size = m.PositionAndShape.Size
      // OSMD SVG backend: 1 unit = 10 SVG px
      const S = 10
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
      rect.setAttribute('x', String(pos.x * S))
      rect.setAttribute('y', String(pos.y * S))
      rect.setAttribute('width', String(size.width * S))
      rect.setAttribute('height', String(size.height * S))
      rect.setAttribute('fill', '#7c3aed')
      rect.setAttribute('fill-opacity', '0.18')
      rect.setAttribute('rx', '3')
      rect.setAttribute('class', 'sori-highlight')
      rect.setAttribute('pointer-events', 'none')
      svg.insertBefore(rect, svg.firstChild)
    }

    // 해당 마디로 자동 스크롤
    const first = staffMeasures[0]
    if (first?.PositionAndShape) {
      const y = first.PositionAndShape.AbsolutePosition.y * 10
      const el = svg.closest('.sheet-scroll') as HTMLElement | null
      el?.scrollTo?.({ top: y - 40, behavior: 'smooth' })
    }
  } catch (e) {
    console.error('highlight error', e)
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
        if (osmdRef.current) highlightMeasure(osmdRef.current, measure)
      },
    }))

    useEffect(() => {
      if (currentMeasure == null || !osmdRef.current) return
      highlightMeasure(osmdRef.current, currentMeasure)
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
      <div className="rounded-xl border border-white/5 bg-white overflow-auto max-h-[60vh] min-h-40 relative sheet-scroll">
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
