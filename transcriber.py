"""transcriber.py - FunASR Paraformer-zh 로컬 음성 인식"""

from pathlib import Path

from cache_manager import CacheManager


class Transcriber:
    """FunASR Paraformer-zh 로컬 음성 인식 (중국어 특화, CPU 가능)"""

    def __init__(self, cache: CacheManager):
        self.cache = cache
        self._model = None

    def _get_model(self):
        if self._model is None:
            from funasr import AutoModel
            self._model = AutoModel(
                model="paraformer-zh",
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                device="cpu",
                disable_update=True,
            )
        return self._model

    def transcribe_file(self, mp3_path: Path) -> str:
        """MP3 파일을 텍스트로 변환 (캐시 확인 포함)"""
        track_name = mp3_path.stem

        cached = self.cache.get_transcription(track_name)
        if cached is not None:
            return cached

        model = self._get_model()
        res = model.generate(input=str(mp3_path), batch_size_s=300)
        text = res[0]["text"] if res and res[0].get("text") else ""

        self.cache.save_transcription(track_name, text)
        return text
