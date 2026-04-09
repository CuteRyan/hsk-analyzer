"""cache_manager.py - JSON 파일 기반 캐싱"""

import json
from dataclasses import asdict

from config import ANALYSIS_CACHE, TRANSCRIPTION_CACHE


class CacheManager:
    def __init__(self):
        TRANSCRIPTION_CACHE.mkdir(parents=True, exist_ok=True)
        ANALYSIS_CACHE.mkdir(parents=True, exist_ok=True)

    def get_transcription(self, track_name: str) -> str | None:
        """캐시된 음성 인식 결과 가져오기"""
        path = TRANSCRIPTION_CACHE / f"{track_name}.json"
        if path.exists():
            data: dict = json.loads(path.read_text(encoding="utf-8"))
            return data.get("text")  # type: ignore[return-value]
        return None

    def save_transcription(self, track_name: str, text: str):
        """음성 인식 결과 캐싱"""
        path = TRANSCRIPTION_CACHE / f"{track_name}.json"
        path.write_text(
            json.dumps({"track": track_name, "text": text}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_analysis(self, track_name: str) -> list[dict] | None:
        """캐시된 분석 결과 가져오기"""
        path = ANALYSIS_CACHE / f"{track_name}.json"
        if path.exists():
            data: dict = json.loads(path.read_text(encoding="utf-8"))
            return data.get("analyses")  # type: ignore[return-value]
        return None

    def save_analysis(self, track_name: str, analyses):
        """분석 결과 캐싱"""
        path = ANALYSIS_CACHE / f"{track_name}.json"
        serialized = [asdict(a) if hasattr(a, "__dataclass_fields__") else a for a in analyses]
        path.write_text(
            json.dumps({"track": track_name, "analyses": serialized}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_processed(self, track_name: str) -> bool:
        """트랙이 이미 처리되었는지 확인"""
        return (TRANSCRIPTION_CACHE / f"{track_name}.json").exists() and (
            ANALYSIS_CACHE / f"{track_name}.json"
        ).exists()
