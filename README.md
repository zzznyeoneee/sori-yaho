# Sori-Yaho

음원(MP3/WAV)을 업로드하면 악기별로 자동 채보하여 MIDI + 악보 파일을 생성하는 웹 서비스.

## 개발 단계

| Phase | 악기 | 상태 |
|---|---|---|
| 1 | 드럼 채보 | 🚧 개발 중 |
| 2 | 기타 코드 채보 | 예정 |
| 3 | 기타 멜로디 TAB | 예정 |

## 빠른 시작

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn main:app --reload
```
→ http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
→ http://localhost:3000

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | Next.js 14 (TypeScript) + Tailwind CSS |
| Backend | FastAPI (Python 3.10+) |
| 트랙 분리 | Demucs |
| 드럼 감지 | madmom, librosa |
| MIDI / 악보 | pretty_midi, music21 |
