'use client'

import { useEffect, useRef } from 'react'

interface TabViewerProps {
  url: string
}

export default function TabViewer({ url }: TabViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const apiRef = useRef<unknown>(null)

  useEffect(() => {
    if (!containerRef.current) return

    let api: unknown = null

    const load = async () => {
      const alphaTab = await import('@coderline/alphatab')
      const at = alphaTab.alphaTab ?? alphaTab.default ?? alphaTab

      const settings = new at.Settings()
      settings.core.engine = 'html5'
      settings.core.logLevel = at.LogLevel?.None ?? 0
      settings.core.fontDirectory = '/font/'
      settings.display.layoutMode = at.LayoutMode?.Page ?? 0
      settings.display.scale = 0.9
      settings.player.enablePlayer = false

      api = new at.AlphaTabApi(containerRef.current!, settings)
      apiRef.current = api

      const res = await fetch(url)
      const buf = await res.arrayBuffer()
      const bytes = new Uint8Array(buf)
      ;(api as any).load(bytes)
    }

    load().catch(console.error)

    return () => {
      try { (apiRef.current as any)?.destroy?.() } catch {}
    }
  }, [url])

  return (
    <div className="bg-white rounded-xl overflow-auto max-h-[500px]">
      <div ref={containerRef} />
    </div>
  )
}
