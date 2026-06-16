# Sori-Yaho

음원(MP3/WAV)을 업로드하면 악기별 MIDI + MusicXML 악보로 자동 변환해주는 웹 서비스입니다.

## 지원 악기

| 악기 | 상태 |
|------|------|
| 🎹 피아노 | ✅ 구현 완료 |
| 🥁 드럼 | ✅ 구현 완료 |
| 🎸 기타 | 🔜 준비 중 |

---

## 사전 요구사항

| 항목 | 버전 | 확인 방법 |
|------|------|-----------|
| Python | 3.11 이상 | `python --version` |
| Node.js | 18 이상 | `node --version` |
| Git | 최신 | `git --version` |
| NVIDIA GPU + CUDA 12.x | 선택사항 (없으면 CPU로 동작) | `nvidia-smi` |

---

## 처음 설치 (최초 1회)

### 1. 저장소 클론

```bash
git clone https://github.com/zzznyeoneee/sori-yaho.git
cd sori-yaho
```

---

### 2. 백엔드 환경 설정

```bash
cd backend
```

#### 가상환경 생성 및 활성화

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Mac / Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

> 활성화되면 터미널 앞에 `(venv)` 가 표시됩니다.

#### 패키지 설치 (순서 중요)

```bash
# 1. PyTorch — NVIDIA GPU 사용 시 (CUDA 12.4)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# CPU만 사용할 경우
pip install torch torchaudio

# 2. 나머지 패키지
pip install -r requirements.txt

# 3. 피아노 채보 모델 (별도 설치)
pip install piano_transcription_inference
```

#### 환경변수 파일 생성

`backend/.env` 파일을 직접 만들고 아래 내용 입력:

**Windows:**
```
UPLOAD_DIR=C:/tmp/sori-yaho/uploads
OUTPUT_DIR=C:/tmp/sori-yaho/outputs
```

**Mac / Linux:**
```
UPLOAD_DIR=/tmp/sori-yaho/uploads
OUTPUT_DIR=/tmp/sori-yaho/outputs
```

---

### 3. 프론트엔드 환경 설정

새 터미널을 열고:

```bash
cd frontend
```

#### 환경변수 파일 생성

`frontend/.env.local` 파일을 만들고 아래 내용 입력:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### 패키지 설치

```bash
npm install
```

---

## 실행 방법 (매번)

**터미널 2개**를 열어서 각각 실행합니다.

### 터미널 1 — 백엔드

```bash
cd backend

# 가상환경 활성화 (Windows)
venv\Scripts\Activate.ps1

# 가상환경 활성화 (Mac/Linux)
source venv/bin/activate

# 서버 시작
python -m uvicorn main:app --reload
```

→ `http://localhost:8000` 에서 실행됩니다.
→ 첫 실행 시 Demucs, piano_transcription 모델 자동 다운로드로 수 분이 걸릴 수 있습니다.

| 주소 | 설명 |
|------|------|
| `http://localhost:8000/health` | 서버 상태 확인 |
| `http://localhost:8000/docs` | API 문서 (Swagger UI) |

---

### 터미널 2 — 프론트엔드

```bash
cd frontend
npm run dev
```

→ `http://localhost:3000` 에서 실행됩니다.

---

## 사용 방법

1. 브라우저에서 `http://localhost:3000` 접속
2. 왼쪽 사이드바에서 악기 선택 (피아노 또는 드럼)
3. MP3 또는 WAV 파일 드래그앤드롭 또는 클릭해서 업로드 (최대 50MB)
4. 변환 완료 후:
   - 악보 미리보기 (MusicXML 렌더링)
   - MIDI 재생 시 현재 마디 하이라이트
   - MIDI / MusicXML 다운로드

---

## 자주 발생하는 문제

### `venv\Scripts\Activate.ps1 cannot be loaded` (Windows)

PowerShell 실행 정책 문제입니다. 아래 명령어를 **관리자 권한**으로 실행:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 백엔드 실행 시 `ModuleNotFoundError`

가상환경이 활성화되지 않은 상태입니다. 터미널 앞에 `(venv)` 가 있는지 확인하고, 없으면 활성화 명령어를 다시 실행하세요.

### 업로드 디렉토리 오류

`.env` 에 설정한 경로가 실제로 존재해야 합니다.

**Windows:**
```powershell
mkdir C:\tmp\sori-yaho\uploads
mkdir C:\tmp\sori-yaho\outputs
```

**Mac / Linux:**
```bash
mkdir -p /tmp/sori-yaho/uploads /tmp/sori-yaho/outputs
```

### 프론트엔드에서 API 연결 안 됨

- 백엔드가 실행 중인지 확인 (`http://localhost:8000/health` 접속)
- `frontend/.env.local` 파일이 있는지 확인
- `.env.local` 수정 후에는 `npm run dev` 재시작 필요

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
│       ├── ResultPanel.tsx    # 결과 패널
│       ├── SheetViewer.tsx    # MusicXML 악보 렌더링
│       └── MidiPlayer.tsx     # MIDI 재생
│
└── backend/                   # FastAPI (Python)
    ├── main.py                # 앱 진입점
    ├── requirements.txt
    ├── .env                   # 환경변수 (직접 생성)
    ├── core/
    │   └── config.py          # 환경 설정
    ├── schemas/
    │   └── transcribe.py      # 요청/응답 모델
    ├── api/routers/
    │   └── transcribe.py      # POST /api/transcribe
    └── instruments/
        ├── drums/
        │   ├── separator.py   # Demucs 트랙 분리
        │   ├── transcriber.py # onset 감지 + 드럼 분류
        │   └── notator.py     # MIDI → MusicXML
        └── piano/
            ├── converter.py   # 오디오 → MIDI → MusicXML
            ├── analyzer.py    # MIDI 파싱 + 손 분리
            └── post_process.py
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js 14, TypeScript, Tailwind CSS |
| 백엔드 | FastAPI, Python 3.11+ |
| 트랙 분리 | Demucs (GPU 가속) |
| 드럼 채보 | librosa, pretty_midi |
| 피아노 채보 | piano_transcription_inference (GPU 가속) |
| 악보 생성 | music21 |
| 악보 렌더링 | OpenSheetMusicDisplay |
| MIDI 재생 | midi-player-js + soundfont-player |
