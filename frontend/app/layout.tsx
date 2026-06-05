import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Sori-Yaho — 음원 자동 채보',
  description: '음원(MP3/WAV)을 업로드하면 악기별 MIDI와 악보로 변환해드립니다.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="antialiased">{children}</body>
    </html>
  )
}
