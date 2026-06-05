export default function Home() {
  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold mb-2">Sori-Yaho</h1>
      <p className="text-gray-400 mb-12 text-lg">음원을 업로드하면 악보로 변환해드려요</p>

      <div className="w-full max-w-xl border-2 border-dashed border-gray-700 rounded-2xl p-12 flex flex-col items-center gap-4 hover:border-gray-500 transition-colors cursor-pointer">
        <div className="text-5xl">🎵</div>
        <p className="text-gray-300 font-medium">MP3 또는 WAV 파일을 드래그하거나 클릭하세요</p>
        <p className="text-gray-600 text-sm">최대 50MB</p>
      </div>

      <div className="flex gap-4 mt-8">
        <button className="px-6 py-2 rounded-full bg-gray-800 text-gray-300 text-sm font-medium hover:bg-gray-700 transition-colors">
<<<<<<< HEAD
          🎹 피아노
        </button>
        <button className="px-6 py-2 rounded-full bg-gray-800 text-gray-300 text-sm font-medium hover:bg-gray-700 transition-colors">
=======
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
          🥁 드럼
        </button>
        <button className="px-6 py-2 rounded-full bg-gray-800 text-gray-300 text-sm font-medium hover:bg-gray-700 transition-colors opacity-50 cursor-not-allowed">
          🎸 기타 (준비 중)
        </button>
      </div>
    </main>
  )
<<<<<<< HEAD
}
=======
}
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
