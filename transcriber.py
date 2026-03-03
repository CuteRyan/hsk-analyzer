"""transcriber.py - Whisper API로 음성 인식"""

import os
import math
import tempfile
from pathlib import Path
from openai import OpenAI

from config import WHISPER_MODEL, MAX_FILE_SIZE_MB, CHUNK_SIZE_MB
from cache_manager import CacheManager


class Transcriber:
    def __init__(self, client: OpenAI, cache: CacheManager):
        self.client = client
        self.cache = cache

    def transcribe_file(self, mp3_path: Path) -> str:
        """MP3 파일을 텍스트로 변환 (캐시 확인 포함)"""
        track_name = mp3_path.stem

        # 캐시 확인
        cached = self.cache.get_transcription(track_name)
        if cached is not None:
            return cached

        file_size_mb = mp3_path.stat().st_size / (1024 * 1024)

        if file_size_mb <= MAX_FILE_SIZE_MB:
            text = self._transcribe_single(mp3_path)
        else:
            text = self._transcribe_chunked(mp3_path)

        # 캐시 저장
        self.cache.save_transcription(track_name, text)
        return text

    def _transcribe_single(self, mp3_path: Path) -> str:
        """25MB 이하 파일 직접 인식"""
        with open(mp3_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
                language="zh",
                prompt="以下是HSK中文听力考试的录音内容。请准确转录所有中文对话和句子。",
                response_format="text",
                temperature=0.0,
            )
        return response

    def _transcribe_chunked(self, mp3_path: Path) -> str:
        """25MB 초과 파일을 분할해서 인식 (pydub + ffmpeg 필요)"""
        try:
            from pydub import AudioSegment
        except ImportError:
            raise RuntimeError(
                "pydub가 설치되지 않았습니다: pip install pydub\n"
                "또한 ffmpeg가 필요합니다: winget install ffmpeg"
            )

        audio = AudioSegment.from_mp3(str(mp3_path))
        duration_ms = len(audio)

        file_size_mb = mp3_path.stat().st_size / (1024 * 1024)
        num_chunks = math.ceil(file_size_mb / CHUNK_SIZE_MB)
        chunk_duration_ms = duration_ms // num_chunks

        full_text_parts = []

        for i in range(num_chunks):
            start = i * chunk_duration_ms
            end = min((i + 1) * chunk_duration_ms, duration_ms)
            chunk = audio[start:end]

            # 임시 파일로 내보내기
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                chunk.export(tmp.name, format="mp3")
                tmp_path = tmp.name

            try:
                # 이전 청크의 끝부분을 컨텍스트로 사용
                context = (full_text_parts[-1][-100:]
                           if full_text_parts
                           else "以下是HSK中文听力考试的录音内容。")

                with open(tmp_path, "rb") as f:
                    response = self.client.audio.transcriptions.create(
                        model=WHISPER_MODEL,
                        file=f,
                        language="zh",
                        prompt=context,
                        response_format="text",
                        temperature=0.0,
                    )
                full_text_parts.append(response)
            finally:
                os.unlink(tmp_path)

        return "\n".join(full_text_parts)
