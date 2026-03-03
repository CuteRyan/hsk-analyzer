"""renderer.py - Jinja2 HTML 렌더링"""

import os
from pathlib import Path
from typing import List
from jinja2 import Environment, FileSystemLoader

from models import TrackAnalysis
from config import OUTPUT_DIR, TEMPLATES_DIR, SOURCE_LABELS


class TrackWithAudio:
    """TrackAnalysis에 audio_path를 추가한 래퍼"""
    def __init__(self, track: TrackAnalysis, audio_path: str):
        self._track = track
        self.audio_path = audio_path

    def __getattr__(self, name):
        return getattr(self._track, name)


class Renderer:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=False
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def render_track(self, track: TrackAnalysis) -> Path:
        """트랙 분석 결과를 HTML로 렌더링"""
        template = self.env.get_template("track.html")
        audio_rel_path = os.path.relpath(
            track.source_path, str(OUTPUT_DIR)
        ).replace("\\", "/")
        html = template.render(track=track, audio_path=audio_rel_path)
        output_path = OUTPUT_DIR / f"{track.track_name}.html"
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def render_combined(self, tracks: List[TrackAnalysis], source: str) -> Path:
        """소스별 전체 트랙을 하나의 HTML로 통합 렌더링"""
        template = self.env.get_template("combined.html")
        title = SOURCE_LABELS.get(source, source)

        track_data = []
        total_sentences = 0
        for t in tracks:
            audio_rel = os.path.relpath(
                t.source_path, str(OUTPUT_DIR)
            ).replace("\\", "/")
            track_data.append(TrackWithAudio(t, audio_rel))
            total_sentences += len(t.sentences)

        html = template.render(
            title=title,
            tracks=track_data,
            total_sentences=total_sentences,
        )
        output_path = OUTPUT_DIR / f"{source}.html"
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def render_index(self, tracks: List[dict]) -> Path:
        """전체 목록 페이지 렌더링"""
        template = self.env.get_template("index.html")
        html = template.render(tracks=tracks)
        output_path = OUTPUT_DIR / "index.html"
        output_path.write_text(html, encoding="utf-8")
        return output_path
