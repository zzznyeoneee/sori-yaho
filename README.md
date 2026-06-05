# Sori-Yaho

음원(MP3/WAV)을 업로드하면 악기별 MIDI + MusicXML 악보로 자동 변환해주는 웹 서비스입니다.

## 지원 악기

| 악기 | 상태 |
|------|------|
| 🎹 피아노 | ✅ 구현 완료 |
| 🥁 드럼 | ✅ 구현 완료 |
| 🎸 기타 | 🔜 준비 중 |

---

## 로컬 실행 방법

### 사전 요구사항

- Python 3.12
- Node.js 18+
- Git
- NVIDIA GPU + CUDA 12.x (선택사항, CPU도 동작)

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
```

#### 패키지 설치 순서 (중요)

```bash
# 1. PyTorch — CUDA 버전 (GPU 사용 시)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# CPU만 사용할 경우
pip install torch torchaudio

# 2. 나머지 패키지
pip install -r requirements.txt

# 3. 피아노 채보 모델 (별도 설치)
pip install piano_transcription_inference
```

#### 설치 패키지 목록

| 패키지 | 용도 |
|--------|------|
| `torch`, `torchaudio` | 딥러닝 프레임워크 (CUDA 지원) |
| `fastapi`, `uvicorn`, `python-multipart` | 웹 서버 |
| `pydantic-settings` | 환경 변수 관리 |
| `demucs` | 트랙 분리 (GPU 가속) |
| `librosa`, `pretty_midi` | 드럼 채보 |
| `music21` | 악보(MusicXML) 생성 |
| `piano_transcription_inference` | 피아노 채보 (GPU 가속) |

#### 백엔드 시작

```bash
python -m uvicorn main:app --reload
```

백엔드가 `http://localhost:8000` 에서 실행됩니다.

> 첫 실행 시 Demucs, piano_transcription 모델 자동 다운로드로 시간이 걸릴 수 있습니다.

- Swagger UI: `http://localhost:8000/docs`
- 헬스체크: `http://localhost:8000/health`

#### Windows 환경변수 (`backend/.env`)

```
UPLOAD_DIR=C:/tmp/sori-yaho/uploads
OUTPUT_DIR=C:/tmp/sori-yaho/outputs
```

---

### 3. 프론트엔드 실행

새 터미널을 열고:

```bash
cd frontend
```

`frontend/.env.local` 파일 생성:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm install
npm run dev
```

프론트엔드가 `http://localhost:3000` 에서 실행됩니다.

#### 프론트엔드 패키지 목록

| 패키지 | 용도 |
|--------|------|
| `next`, `react`, `typescript` | 프레임워크 |
| `tailwindcss` | 스타일 |
| `opensheetmusicdisplay` | MusicXML 악보 렌더링 |
| `midi-player-js` | MIDI 재생 |
| `soundfont-player` | 가상악기 사운드 |

---

### 4. 사용 방법

1. 브라우저에서 `http://localhost:3000` 접속
2. 왼쪽 사이드바에서 악기 선택 (피아노 또는 드럼)
3. MP3 또는 WAV 파일 드래그앤드롭 또는 클릭해서 업로드
4. 변환 완료 후:
   - 악보 미리보기 (MusicXML 렌더링)
   - MIDI 재생 시 현재 마디 표시
   - MIDI / MusicXML 다운로드

---

## 프로젝트 구조

```
sori-yaho/
├── frontend/                  # Next.js 14 (TypeScript)
│   ├── app/
│   │   ├── page.tsx           # 메인 페이지 (2열 레이아웃)
│   │   └── layout.tsx
│   └── components/
│       ├── Sidebar.tsx        # 악기 선택
│       ├── UploadZone.tsx     # 파일 업로드
│       ├── ProgressCard.tsx   # 변환 진행 상태
│       ├── ResultPanel.tsx    # 결과 통합 패널
│       ├── SheetViewer.tsx    # MusicXML 악보 렌더링 + 마디 커서
│       └── MidiPlayer.tsx     # MIDI 재생 + 마디 동기화
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
        │   ├── separator.py   # Demucs 트랙 분리 (GPU)
        │   ├── transcriber.py # onset 감지 + kick/snare/hihat 분류
        │   └── notator.py     # MIDI → MusicXML
        └── piano/
            ├── converter.py   # 오디오 → MIDI → MusicXML (GPU)
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
| 백엔드 | FastAPI, Python 3.12 |
| 트랙 분리 | Demucs (GPU 가속) |
| 드럼 채보 | librosa, pretty_midi |
| 피아노 채보 | piano_transcription_inference (GPU 가속) |
| 악보 생성 | music21 |
| 악보 렌더링 | OpenSheetMusicDisplay |
| MIDI 재생 | midi-player-js + soundfont-player |
