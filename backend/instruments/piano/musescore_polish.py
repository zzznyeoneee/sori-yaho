"""
MuseScore CLI 폴리싱 스텝.

MusicXML 파일을 입력받아 MuseScore 4 / 3 CLI로:
  1. 정리된 MusicXML 재출력 (beam grouping, tie, spacing 자동 보정)
  2. 인쇄용 PDF 생성

MuseScore 미설치 또는 변환 실패 시 (None, None) 반환 — 예외를 raise하지 않음.

Public API:
    find_musescore() -> str | None
    polish(xml_path, output_dir) -> tuple[str | None, str | None]
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Windows 표준 설치 경로 (MuseScore 4 우선)
_WINDOWS_CANDIDATES: list[str] = [
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
    r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
    r"C:\Program Files (x86)\MuseScore 4\bin\MuseScore4.exe",
    r"C:\Program Files (x86)\MuseScore 3\bin\MuseScore3.exe",
]

# PATH 탐색용 이름 (Linux/macOS + 비표준 설치)
_PATH_CANDIDATES: list[str] = [
    "mscore4", "MuseScore4",
    "mscore3", "MuseScore3",
    "mscore",  "MuseScore",
]


def find_musescore() -> str | None:
    """
    MuseScore 실행 파일을 자동 탐색.

    탐색 순서:
      1. MUSESCORE_PATH 설정값 (비어있지 않은 경우)
      2. Windows 하드코딩 경로 (MuseScore 4 우선)
      3. PATH 환경변수 (크로스 플랫폼 / 비표준 설치)

    Returns
    -------
    첫 번째로 발견된 실행 파일 경로, 없으면 None.
    """
    from core.config import settings

    # 1. 명시적 설정 우선
    if settings.MUSESCORE_PATH:
        p = Path(settings.MUSESCORE_PATH)
        if p.exists():
            return str(p)
        logger.warning(
            "MUSESCORE_PATH=%s 가 존재하지 않습니다. 자동 탐색으로 전환합니다.", p
        )

    # 2. Windows 하드코딩 경로
    for candidate in _WINDOWS_CANDIDATES:
        if Path(candidate).exists():
            logger.debug("MuseScore 발견 (하드코딩): %s", candidate)
            return candidate

    # 3. PATH 검색
    for name in _PATH_CANDIDATES:
        found = shutil.which(name)
        if found:
            logger.debug("MuseScore 발견 (PATH): %s", found)
            return found

    return None


def _get_musescore_version(exe: str) -> int:
    """MuseScore 실행 파일의 메이저 버전 번호 반환 (3 또는 4, 알 수 없으면 3)."""
    try:
        r = subprocess.run(
            [exe, "--version"],
            capture_output=True, timeout=10,
        )
        out = (r.stdout or r.stderr or b"").decode(errors="replace")
        if "4." in out or "MuseScore 4" in out:
            return 4
    except Exception:
        pass
    return 3


def _build_cmd(exe: str, out_path: str, in_path: str, version: int) -> list[str]:
    """MuseScore 버전에 맞는 CLI 명령 구성.

    - MuseScore 3: --no-gui 플래그로 headless 실행 가능
    - MuseScore 4: --no-gui 미지원, -j (job file) 방식 대신 직접 -o 사용
      (rc=1320 이 나오는 경우 MuseScore 4가 GUI 세션 없이 실행되는 것이 원인)
    """
    if version == 3:
        # MuseScore 3는 --no-gui 로 헤드리스 실행 지원
        return [exe, "--no-gui", "-o", out_path, in_path]
    else:
        # MuseScore 4: -o 직접 사용 (GUI 세션 필요할 수 있음)
        return [exe, "-o", out_path, in_path]


def _run_musescore(cmd: list[str], label: str, out_path: Path) -> str | None:
    """MuseScore 변환 명령 실행 및 결과 경로 반환."""
    try:
        result = subprocess.run(
            cmd,
            check=True,
            timeout=120,
            capture_output=True,
        )
        if out_path.exists():
            logger.info("MuseScore %s 완료: %s", label, out_path)
            return str(out_path)
        stdout = result.stdout.decode(errors="replace") if result.stdout else ""
        stderr = result.stderr.decode(errors="replace") if result.stderr else ""
        logger.warning(
            "MuseScore %s: 실행 성공했으나 출력 파일 없음.\nstdout: %s\nstderr: %s",
            label, stdout[:400], stderr[:400],
        )
    except subprocess.TimeoutExpired:
        logger.warning("MuseScore %s 타임아웃 (120초). MuseScore 4 headless 미지원일 수 있음.", label)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        stdout = exc.stdout.decode(errors="replace") if exc.stdout else ""
        logger.warning(
            "MuseScore %s 실패 (rc=%d).\n"
            "  원인: MuseScore 4는 GUI 세션 없이 실행 불가 (rc=1320 등)\n"
            "  해결: MuseScore 3 설치 또는 MUSESCORE_POLISH_ENABLED=false\n"
            "  stdout: %s\n  stderr: %s",
            label, exc.returncode, stdout[:400], stderr[:400],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("MuseScore %s 오류: %s", label, exc)
    return None


def polish(
    xml_path: str,
    output_dir: str,
) -> tuple[str | None, str | None]:
    """
    MuseScore CLI로 MusicXML 정리 + PDF 생성.

    Parameters
    ----------
    xml_path   : 입력 MusicXML 파일 경로.
    output_dir : 출력 파일을 저장할 디렉터리.

    Returns
    -------
    (polished_xml_path, pdf_path)
        파일이 생성된 경우 절대 경로 문자열, 실패/미설치 시 None.

    Notes
    -----
    MuseScore 4는 GUI 세션 없이 실행 시 rc=1320 오류가 발생할 수 있다.
    이 경우 MuseScore 3를 설치하거나 MUSESCORE_POLISH_ENABLED=false로 비활성화.
    """
    from core.config import settings

    if not settings.MUSESCORE_POLISH_ENABLED:
        logger.debug("MUSESCORE_POLISH_ENABLED=false — 폴리싱 스킵.")
        return None, None

    exe = find_musescore()
    if exe is None:
        logger.info("MuseScore를 찾을 수 없습니다. 폴리싱 스킵.")
        return None, None

    version    = _get_musescore_version(exe)
    out_dir    = Path(output_dir)
    stem       = Path(xml_path).stem
    polish_xml = out_dir / f"{stem}_polished.xml"
    polish_pdf = out_dir / f"{stem}.pdf"

    logger.info("MuseScore %d 사용: %s", version, exe)

    polished_xml_result = _run_musescore(
        _build_cmd(exe, str(polish_xml), xml_path, version),
        "XML 폴리싱", polish_xml,
    )
    pdf_result = _run_musescore(
        _build_cmd(exe, str(polish_pdf), xml_path, version),
        "PDF 생성", polish_pdf,
    )

    return polished_xml_result, pdf_result
