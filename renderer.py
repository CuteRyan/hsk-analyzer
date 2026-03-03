"""renderer.py - Jinja2 HTML 렌더링"""

import os
from pathlib import Path
from typing import List
from jinja2 import Environment, FileSystemLoader

from models import TrackAnalysis
from config import OUTPUT_DIR, TEMPLATES_DIR


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
        # MP3 파일의 상대 경로 계산 (output/ → MP3 소스)
        audio_rel_path = os.path.relpath(
            track.source_path, str(OUTPUT_DIR)
        ).replace("\\", "/")
        html = template.render(track=track, audio_path=audio_rel_path)
        output_path = OUTPUT_DIR / f"{track.track_name}.html"
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def render_index(self, tracks: List[dict]) -> Path:
        """전체 목록 페이지 렌더링"""
        template = self.env.get_template("index.html")
        html = template.render(tracks=tracks)
        output_path = OUTPUT_DIR / "index.html"
        output_path.write_text(html, encoding="utf-8")
        return output_path
