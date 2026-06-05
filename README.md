# Sori-Yaho

음원(MP3/WAV)을 업로드하면 악기별 MIDI + MusicXML 악보로 자동 변환해주는 웹 서비스입니다.

## 지원 악기

| 악기 | 상태 |
|------|------|
| 🥁 드럼 | ✅ 구현 완료 |
| 🎹 피아노 | ✅ 구현 완료 |
| 🎸 기타 | 🔜 준비 중 |

---

## 로컬 실행 방법

### 사전 요구사항

- Python 3.10+
- Node.js 18+
- Git

---

### 1. 저장소 클론

```bash
git clone https://github.com/zzznyeoneee/sori-yaho.git
cd sori-yaho
git checkout claude/laughing-cray-MOupG
```

---

### 2. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

백엔드가 `http://localhost:8000` 에서 실행됩니다.

> 첫 실행 시 Demucs, Basic Pitch 모델 다운로드로 시간이 걸릴 수 있습니다.

**API 확인:**
- Swagger UI: `http://localhost:8000/docs`
- 헬스체크: `http://localhost:8000/health`

---

### 3. 프론트엔드 실행

새 터미널을 열고:

```bash
cd frontend
```

`.env.local` 파일 생성:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

패키지 설치 및 실행:

```bash
npm install
npm run dev
```

프론트엔드가 `http://localhost:3000` 에서 실행됩니다.

---

### 4. 사용 방법

1. 브라우저에서 `http://localhost:3000` 접속
2. 왼쪽 사이드바에서 악기 선택 (드럼 또는 피아노)
3. MP3 또는 WAV 파일 드래그앤드롭 또는 클릭해서 업로드
4. 변환 완료 후 MIDI / MusicXML 다운로드

---

## 프로젝트 구조

```
sori-yaho/
├── frontend/                  # Next.js 14 (TypeScript)
│   ├── app/
│   │   ├── page.tsx           # 메인 페이지
│   │   └── layout.tsx
│   └── components/
│       ├── Sidebar.tsx        # 악기 선택
│       ├── UploadZone.tsx     # 파일 업로드
│       ├── ProgressCard.tsx   # 변환 진행 상태
│       └── ResultPanel.tsx    # MIDI 플레이어 + 다운로드
│
└── backend/                   # FastAPI (Python)
    ├── main.py                # 앱 진입점
    ├── requirements.txt
    ├── core/
    │   └── config.py          # 환경 설정
    ├── schemas/
    │   └── transcribe.py      # 요청/응답 모델
    ├── api/routers/
    │   └── transcribe.py      # POST /api/transcribe
    └── instruments/
        ├── drums/
        │   ├── separator.py   # Demucs 트랙 분리
        │   ├── transcriber.py # onset 감지 + kick/snare/hihat 분류
        │   └── notator.py     # MIDI → MusicXML
        └── piano/
            ├── converter.py   # 오디오 → MIDI → MusicXML
            ├── analyzer.py    # MIDI 파싱 + 손 분리
            ├── post_process.py
            ├── basicpitch_adapter.py
            └── musescore_polish.py
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js 14, TypeScript, Tailwind CSS |
| 백엔드 | FastAPI, Python 3.10+ |
| 트랙 분리 | Demucs |
| 드럼 감지 | librosa, pretty_midi |
| 피아노 채보 | Basic Pitch (Spotify) |
| 악보 생성 | music21 |

---

## 환경 변수

### 프론트엔드 (`frontend/.env.local`)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | 백엔드 API 주소 |

### 백엔드 (`backend/.env`, 선택사항)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `UPLOAD_DIR` | `/tmp/sori-yaho/uploads` | 업로드 파일 저장 경로 |
| `OUTPUT_DIR` | `/tmp/sori-yaho/outputs` | 변환 결과 저장 경로 |
| `MAX_FILE_SIZE_MB` | `50` | 최대 업로드 파일 크기 |
| `TRANSCRIPTION_MODEL` | `basic_pitch` | 피아노 채보 모델 |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | 허용할 CORS 출처 |
