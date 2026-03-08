"""renderer.py - Jinja2 HTML 렌더링"""

import json
import os
import re
from pathlib import Path
from typing import List
from jinja2 import Environment, FileSystemLoader

from models import TrackAnalysis, SentenceAnalysis, WordBreakdown, GrammarPoint
from config import OUTPUT_DIR, TEMPLATES_DIR, SOURCE_LABELS, TRANSCRIPTION_CACHE, ANALYSIS_CACHE


# 중국어 숫자 → 정수 변환
_CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
           '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def _chinese_to_int(s: str) -> int:
    """중국어 숫자를 정수로 변환 (一~九十九)"""
    if not s:
        return 0
    result = 0
    for ch in s:
        if ch == '十':
            result = (result or 1) * 10
        else:
            result += _CN_NUM.get(ch, 0)
    return result


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

    def _group_by_questions(self, track: TrackAnalysis) -> list:
        """트랙을 시험 마커 기준으로 문제별 그룹화.
        반환: [{"question_num": int|None, "sentences": [...]}]
        """
        transcription = track.transcription or ""
        sentences = list(track.sentences)

        if not sentences:
            return [{"question_num": None, "sentences": []}]

        # 트랜스크립션에서 문제 번호 마커 찾기
        marker_re = re.compile(
            r'(?:^|(?<=[。？！?!\s]))'
            r'\s*'
            r'(?:'
            r'([一二三四五六七八九十]{1,3})'
            r'|(\d{1,2})'
            r')'
            r'(?=[。.\s、])'
        )

        markers = []
        for m in marker_re.finditer(transcription):
            cn, ar = m.group(1), m.group(2)
            num = _chinese_to_int(cn) if cn else int(ar)
            markers.append((m.start(), num))

        if len(markers) < 2:
            return [{"question_num": None, "sentences": sentences}]

        # 순차 번호 확인 (중복 허용하되, 감소는 불허)
        nums = [n for _, n in markers]
        if not all(nums[i] <= nums[i + 1] for i in range(len(nums) - 1)):
            return [{"question_num": None, "sentences": sentences}]

        # 중복 마커 제거 (Whisper hallucination): 같은 번호가 반복되면 첫 번째만
        seen = set()
        unique_markers = []
        for pos, num in markers:
            if num not in seen:
                seen.add(num)
                unique_markers.append((pos, num))
        markers = unique_markers

        if len(markers) < 2:
            return [{"question_num": None, "sentences": sentences}]

        # 각 문장의 트랜스크립션 내 위치 찾기
        # GPT가 "11. " 같은 번호를 붙이는 경우 제거 후 검색
        sentence_positions = []
        search_from = 0
        for s in sentences:
            clean = re.sub(r'^\d+\.\s*', '', s.original)
            pos = transcription.find(clean, search_from)
            if pos >= 0:
                sentence_positions.append(pos)
                search_from = pos + len(clean)
            else:
                # 첫 20자로 재시도
                short = clean[:20]
                pos2 = transcription.find(short, search_from)
                if pos2 >= 0:
                    sentence_positions.append(pos2)
                    search_from = pos2 + len(short)
                else:
                    sentence_positions.append(search_from)

        # 마커별로 문장 그룹화
        groups = []
        for i, (marker_pos, num) in enumerate(markers):
            next_pos = (markers[i + 1][0]
                        if i + 1 < len(markers) else len(transcription))
            group_sents = [
                s for s, pos in zip(sentences, sentence_positions)
                if marker_pos <= pos < next_pos
            ]
            if group_sents:
                groups.append({"question_num": num, "sentences": group_sents})

        # 첫 마커 이전 문장 (도입부)
        pre = [s for s, pos in zip(sentences, sentence_positions)
               if pos < markers[0][0]]
        if pre:
            groups.insert(0, {"question_num": 0, "sentences": pre})

        return groups if len(groups) > 1 else [
            {"question_num": None, "sentences": sentences}]

    def _load_split_track(self, sub_name: str) -> TrackAnalysis:
        """분할 캐시(TRACK010-1.json 등)에서 TrackAnalysis 로드"""
        trans_file = TRANSCRIPTION_CACHE / f"{sub_name}.json"
        anal_file = ANALYSIS_CACHE / f"{sub_name}.json"

        transcription = ""
        if trans_file.exists():
            with open(trans_file, encoding="utf-8") as f:
                transcription = json.load(f).get("text", "")

        sentences = []
        if anal_file.exists():
            with open(anal_file, encoding="utf-8") as f:
                data = json.load(f)
            for s in data.get("analyses", []):
                words = [WordBreakdown(**w) if isinstance(w, dict) else w
                         for w in s.get("words", [])]
                grammar = [GrammarPoint(**g) if isinstance(g, dict) else g
                           for g in s.get("grammar_points", [])]
                sentences.append(SentenceAnalysis(
                    sentence_index=s["sentence_index"],
                    original=s["original"],
                    pinyin_full=s["pinyin_full"],
                    words=words,
                    grammar_points=grammar,
                    translation_ko=s["translation_ko"],
                    translation_literal_ko=s["translation_literal_ko"],
                    difficulty_note=s["difficulty_note"],
                    role=s.get("role", ""),
                ))

        return TrackAnalysis(
            track_name=sub_name,
            source_path="",
            transcription=transcription,
            sentences=sentences,
            total_duration_hint="",
            processing_timestamp="cached",
        )

    def _load_split_caches(self, track_name: str) -> list:
        """분할 캐시에서 문제별 분석 로드.
        반환: [{"question_num": int, "sentences": [...]}] (번호순 정렬)
        """
        import glob as globmod
        pattern = str(ANALYSIS_CACHE / f"{track_name}-*.json")
        split_files = sorted(globmod.glob(pattern))

        if not split_files:
            return []

        questions = []
        for anal_path in split_files:
            sub_name = Path(anal_path).stem  # TRACK010-1
            match = re.match(r'.+-(\d+)$', sub_name)
            if not match:
                continue
            q_num = int(match.group(1))

            sub_track = self._load_split_track(sub_name)
            if not sub_track.sentences:
                continue

            questions.append({
                "question_num": q_num,
                "sentences": list(sub_track.sentences),
            })

        # 번호순 정렬
        questions.sort(key=lambda q: q["question_num"])
        return questions

    def _load_questions_from_transcription(self, track_name: str,
                                             sentences: List[SentenceAnalysis]) -> list:
        """transcription JSON의 questions 배열을 읽어서
        analysis의 SentenceAnalysis 객체와 매칭하여 문제별 그룹 반환.
        반환: [{"question_num": int, "sentences": [SentenceAnalysis, ...]}]
        """
        trans_file = TRANSCRIPTION_CACHE / f"{track_name}.json"
        if not trans_file.exists():
            return []

        with open(trans_file, encoding="utf-8") as f:
            trans_data = json.load(f)

        questions = trans_data.get("questions", [])
        if not questions:
            return []

        # sentence_index → SentenceAnalysis 맵
        sent_map = {s.sentence_index: s for s in sentences}

        result = []
        for q in questions:
            q_sents = []
            for qs in q.get("sentences", []):
                idx = qs.get("index")
                if idx is not None and idx in sent_map:
                    q_sents.append(sent_map[idx])
            if q_sents:
                # 분할 오디오 파일 확인
                q_num = q["question_num"]
                split_audio = OUTPUT_DIR / "audio_splits" / f"{track_name}-{q_num:02d}.mp3"
                audio_path = ""
                if split_audio.exists():
                    audio_path = os.path.relpath(
                        str(split_audio), str(OUTPUT_DIR)
                    ).replace("\\", "/")
                result.append({
                    "question_num": q_num,
                    "sentences": q_sents,
                    "audio_path": audio_path,
                })

        return result

    def render_split_tracks(self, tracks: List[TrackAnalysis]) -> List[Path]:
        """분할된 문제별 트랙의 개별 HTML 생성.
        transcription 캐시에서 parent_track이 있는 분할 트랙을 찾아 렌더링.
        """
        import glob as globmod
        template = self.env.get_template("track.html")
        rendered = []

        parent_names = {t.track_name for t in tracks}

        for parent in sorted(parent_names):
            pattern = str(TRANSCRIPTION_CACHE / f"{parent}-*.json")
            split_files = sorted(globmod.glob(pattern))
            if not split_files:
                continue

            for trans_path in split_files:
                sub_name = Path(trans_path).stem
                sub_track = self._load_split_track(sub_name)
                if not sub_track.sentences:
                    continue

                # 부모 트랙의 source_path로 오디오 경로 설정 (원본 전체 오디오)
                parent_track = next((t for t in tracks if t.track_name == parent), None)
                audio_rel = ""
                if parent_track:
                    audio_rel = os.path.relpath(
                        parent_track.source_path, str(OUTPUT_DIR)
                    ).replace("\\", "/")

                # 개별 HTML에 parent_track, question_num 정보 전달
                with open(trans_path, encoding="utf-8") as f:
                    trans_data = json.load(f)

                html = template.render(
                    track=sub_track,
                    audio_path=audio_rel,
                    parent_track=parent,
                    question_num=trans_data.get("question_num", 0),
                )
                output_path = OUTPUT_DIR / f"{sub_name}.html"
                output_path.write_text(html, encoding="utf-8")
                rendered.append(output_path)

        return rendered

    def render_combined(self, tracks: List[TrackAnalysis], source: str) -> Path:
        """소스별 전체 트랙을 하나의 HTML로 통합 렌더링.
        - transcription JSON에 questions 배열이 있으면 문제별 그룹화
        - 없으면 기존 방식 (하나의 섹션)"""
        template = self.env.get_template("combined.html")
        title = SOURCE_LABELS.get(source, source)

        track_data = []
        total_sentences = 0

        for t in tracks:
            audio_rel = os.path.relpath(
                t.source_path, str(OUTPUT_DIR)
            ).replace("\\", "/")

            # transcription JSON의 questions 배열에서 문제별 그룹화
            questions = self._load_questions_from_transcription(
                t.track_name, list(t.sentences))

            tw = TrackWithAudio(t, audio_rel)
            tw.questions = questions if questions else None
            track_data.append(tw)
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
