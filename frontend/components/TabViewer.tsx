'use client'

import { useEffect, useRef, useState } from 'react'

interface TabViewerProps {
  url: string
}

declare global {
  interface Window {
    alphaTab: any
  }
}

export default function TabViewer({ url }: TabViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const apiRef = useRef<any>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    if (!containerRef.current) return

    const loadAlphaTab = () => {
      return new Promise<void>((resolve, reject) => {
        if (window.alphaTab) { resolve(); return }

        const script = document.createElement('script')
        script.src = '/alphaTab.js'
        script.onload = () => resolve()
        script.onerror = () => reject(new Error('alphaTab CDN 로드 실패'))
        document.head.appendChild(script)
      })
    }

    const init = async () => {
      try {
        await loadAlphaTab()
        const at = window.alphaTab

        const settings = new at.Settings()
        settings.core.engine = 'html5'
        settings.core.logLevel = at.LogLevel.None
        settings.core.fontDirectory = '/font/'
        settings.display.layoutMode = at.LayoutMode.Page
        settings.display.scale = 0.9
        settings.player.enablePlayer = false

        const api = new at.AlphaTabApi(containerRef.current!, settings)
        apiRef.current = api

        api.renderFinished.on(() => setStatus('ready'))

        const res = await fetch(url)
        const buf = await res.arrayBuffer()
        api.load(new Uint8Array(buf))
      } catch (e) {
        console.error(e)
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
        <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm">
          타브 악보 로드 실패
        </div>
      )}
      <div ref={containerRef} />
    </div>
  )
}
