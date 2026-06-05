<<<<<<< HEAD
﻿# 01. ?꾨줈?앺듃 媛쒖슂 諛??꾪궎?띿쿂

## ?쒕퉬???뚭컻

**?쒕퉬?ㅻ챸:** Sori-Yaho

**紐⑹쟻:**
?뚯썝(MP3/WAV)???낅줈?쒗븯硫??낃린蹂꾨줈 ?먮룞 梨꾨낫?섏뿬 MIDI + ?낅낫(MusicXML) ?뚯씪???앹꽦?쒕떎.

## 媛쒕컻 ?④퀎

| Phase | ?낃린 | ?듭떖 湲곕뒫 |
|---|---|---|
| 1 | ?쒕읆 | ?ㅻ뵒?????쒕읆 ?몃옓 遺꾨━ ??MIDI + ?낅낫 ?앹꽦 |
| 2 | 湲고? | ?ㅻ뵒????肄붾뱶 吏꾪뻾 梨꾨낫 ??肄붾뱶 李⑦듃 ?앹꽦 |
| 3 | 湲고? ?뺤옣 | 硫쒕줈??TAB ?앹꽦 |

## ?곗씠???먮쫫
1.?ъ슜?먭? MP3/WAV ?낅줈??
2.POST /api/upload ???뚯씪 ??? task_id 諛쒓툒
3.POST /api/separate ??Demucs濡??낃린 ?몃옓 遺꾨━
4.POST /api/transcribe ???쒕읆: onset detection ??MIDI
5.POST /api/notate ??MIDI ??MusicXML ?낅낫 ?앹꽦
6.GET /api/result/{id} ???꾨즺 ??寃곌낵 ?쒖떆
7.GET /api/download/.. ??MIDI / MusicXML ?ㅼ슫濡쒕뱶

## 湲곗닠 ?ㅽ깮
| 援щ텇 | 湲곗닠 |
|---|---|
| Frontend | Next.js 14 (TypeScript) + Tailwind CSS |
| Backend | FastAPI (Python 3.10+) |
| ?몃옓 遺꾨━ | Demucs |
| ?쒕읆 媛먯? | madmom, librosa |
| MIDI / ?낅낫 | pretty_midi, music21 |
=======
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
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
