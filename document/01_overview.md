# 01. 프로젝트 개요 및 아키텍처

## 서비스 소개

**서비스명:** Sori-Yaho

**목적:**
음원(MP3/WAV)을 업로드하면 악기별로 자동 채보하여 MIDI + 악보(MusicXML) 파일을 생성한다.

---

## 개발 단계

| Phase | 악기 | 핵심 기능 |
|---|---|---|
| 1 | 드럼 | 오디오 → 드럼 트랙 분리 → MIDI + 악보 생성 |
| 2 | 기타 | 오디오 → 코드 진행 채보 → 코드 차트 생성 |
| 3 | 기타 확장 | 멜로디 TAB 생성 |

---

## 데이터 흐름

```
1. 사용자가 MP3/WAV 업로드
        ↓
2. POST /api/upload      → 파일 저장, task_id 발급
        ↓
3. POST /api/separate    → Demucs로 악기 트랙 분리
        ↓
4. POST /api/transcribe  → 드럼: onset detection → MIDI
                           기타: chord detection → 코드 차트
        ↓
5. POST /api/notate      → MIDI → MusicXML 악보 생성
        ↓
6. GET  /api/result/{id} → 완료 시 결과 표시
        ↓
7. GET  /api/download/.. → MIDI / MusicXML 다운로드
```

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | Next.js 14 (TypeScript) + Tailwind CSS |
| Backend | FastAPI (Python 3.10+) |
| 트랙 분리 | Demucs |
| 드럼 감지 | madmom, librosa |
| 기타 코드 | librosa (chroma), basic-pitch |
| MIDI / 악보 | pretty_midi, music21, mido |
| 배포 FE | Vercel |
| 배포 BE | AWS EC2 + nginx |

---

## 백엔드 폴더 구조

```
backend/
  main.py
  core/
    config.py
  schemas/
    transcribe.py
  api/
    routers/
      upload.py
      transcribe.py
      result.py
  instruments/
    drums/
      separator.py     # Demucs 드럼 분리
      transcriber.py   # onset detection → MIDI
      notator.py       # MIDI → MusicXML
    guitar/            # Phase 2
      separator.py
      chord_detector.py
      tab_generator.py  # Phase 3
  services/
```
