'use client'

import { useEffect, useRef, useState } from 'react'

interface TabViewerProps {
  url: string
}

export default function TabViewer({ url }: TabViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const apiRef = useRef<any>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!containerRef.current) return

    const init = async () => {
      try {
        const at = (await import('@coderline/alphatab')) as any

        const settings = new at.Settings()
        // Disable workers — worker path auto-detection fails in Next.js dev/build
        settings.core.useWorkers = false
        settings.core.logLevel = at.LogLevel.Warning
        // Load Bravura fonts from CDN (cached after first load)
        settings.core.fontDirectory =
          'https://cdn.jsdelivr.net/npm/@coderline/alphatab@1.8.3/dist/font/'
        settings.display.layoutMode = at.LayoutMode.Page
        settings.display.scale = 0.9
        settings.player.enablePlayer = false

        const api = new at.AlphaTabApi(containerRef.current!, settings)
        apiRef.current = api

        api.renderFinished.on(() => setStatus('ready'))
        api.postRenderFinished.on(() => setStatus('ready'))
        api.error.on((e: any) => {
          console.error('alphaTab error:', e)
          setErrorMsg(e?.message ?? String(e))
          setStatus('error')
        })

        const res = await fetch(url)
        if (!res.ok) throw new Error(`파일 로드 실패: ${res.status}`)
        const buf = await res.arrayBuffer()
        api.load(new Uint8Array(buf))
      } catch (e) {
        console.error('TabViewer init error:', e)
        setErrorMsg(e instanceof Error ? e.message : String(e))
        setStatus('error')
      }
    }

    init()

    return () => {
      try { apiRef.current?.destroy?.() } catch {}
    }
  }, [url])

  return (
    <div className="bg-white rounded-xl overflow-auto max-h-[500px] min-h-[200px] relative">
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
          타브 악보 로딩 중...
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center flex-col gap-1">
          <span className="text-red-400 text-sm">타브 악보 로드 실패</span>
          {errorMsg && <span className="text-red-300 text-xs px-4 text-center">{errorMsg}</span>}
        </div>
      )}
      <div ref={containerRef} />
    </div>
  )
}
