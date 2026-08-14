"""Kokoro TTS speech service for manim-voiceover.

Ported from the TheoremExplainAgent OpenStax fork (src/utils/kokoro_voiceover.py,
originally (c) 2025 Xposed73, Manim Voiceover project). Changes here:
- configured via environment variables instead of a Config class, because this
  file is copied next to each generated scene and imported standalone;
- a KNOWN_VOICES registry + validate_voice() so the pipeline can assign one
  distinct voice per scenario character and fall back safely.

The speech cache key (get_data_hash input) includes the voice, so switching
voices between voiceover blocks caches correctly.
"""

import hashlib
import json
import os

import numpy as np
from pathlib import Path
from manim_voiceover.services.base import SpeechService
from manim_voiceover.helper import remove_bookmarks, wav2mp3
from scipy.io.wavfile import write as write_wav

try:
    from kokoro_onnx import Kokoro
except ImportError:  # kokoro not installed -> silent fallback below
    Kokoro = None

# Kokoro v0.19 voice names. a*=American, b*=British; f/m = presented voice.
KNOWN_VOICES = [
    "af",
    "af_bella",
    "af_nicole",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_michael",
    "bf_emma",
    "bf_isabella",
    "bm_george",
    "bm_lewis",
]

DEFAULT_MODEL_PATH = os.environ.get("KOKORO_MODEL_PATH", "models/kokoro-v0_19.onnx")
DEFAULT_VOICES_PATH = os.environ.get("KOKORO_VOICES_PATH", "models/voices.bin")
DEFAULT_VOICE = os.environ.get("KOKORO_DEFAULT_VOICE", "af_sarah")
DEFAULT_SPEED = float(os.environ.get("KOKORO_DEFAULT_SPEED", "1.0"))
DEFAULT_LANG = os.environ.get("KOKORO_DEFAULT_LANG", "en-us")


def validate_voice(voice: str) -> str:
    """Return the voice if known, else the default (with a warning)."""
    if voice in KNOWN_VOICES:
        return voice
    print(f"[kokoro] Unknown voice '{voice}', falling back to {DEFAULT_VOICE}")
    return DEFAULT_VOICE


class KokoroService(SpeechService):
    """Speech service backed by Kokoro ONNX, with per-call voice switching."""

    def __init__(
        self,
        engine=None,
        model_path: str = DEFAULT_MODEL_PATH,
        voices_path: str = DEFAULT_VOICES_PATH,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
        lang: str = DEFAULT_LANG,
        **kwargs,
    ):
        # Silent fallback: when the Kokoro model files (or the package) are
        # missing, keep the VoiceoverScene contract intact by emitting silence
        # of the estimated speech duration instead of failing the render.
        if (
            Kokoro is not None
            and os.path.exists(model_path)
            and os.path.exists(voices_path)
        ):
            self.kokoro = Kokoro(model_path, voices_path)
        else:
            print(
                f"[kokoro] model files unavailable ({model_path}, {voices_path}) "
                "— generating SILENT voiceover tracks"
            )
            self.kokoro = None
        self.voice = validate_voice(voice)
        self.speed = speed
        self.lang = lang

        if engine is None:
            engine = self.text_to_speech

        self.engine = engine
        super().__init__(**kwargs)

    def set_voice(self, voice: str):
        """Switch the speaking voice for subsequent voiceover blocks."""
        self.voice = validate_voice(voice)

    def get_data_hash(self, input_data: dict) -> str:
        data_str = json.dumps(input_data, sort_keys=True)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    def text_to_speech(self, text, output_file, voice_name, speed, lang):
        """Generate speech via Kokoro ONNX, normalize, save as .wav. Without a
        Kokoro model, write silence sized to ~2.7 words/sec speech rate."""
        if self.kokoro is None:
            sample_rate = 24000
            duration_s = max(1.0, len(text.split()) / 2.7) / max(speed, 0.1)
            samples = np.zeros(int(sample_rate * duration_s), dtype=np.float32)
            write_wav(output_file, sample_rate, (samples * 32767).astype("int16"))
            return output_file
        samples, sample_rate = self.kokoro.create(
            text, voice=voice_name, speed=speed, lang=lang
        )
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples = samples / max_val
        samples = (samples * 32767).astype("int16")
        write_wav(output_file, sample_rate, samples)
        return output_file

    def generate_from_text(
        self, text: str, cache_dir: str = None, path: str = None
    ) -> dict:
        if cache_dir is None:
            cache_dir = self.cache_dir

        input_data = {
            "input_text": text,
            "service": "kokoro_self",
            "voice": self.voice,
            "lang": self.lang,
        }
        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result

        if path is None:
            audio_path = self.get_data_hash(input_data) + ".mp3"
        else:
            audio_path = path

        audio_path_wav = str(Path(cache_dir) / audio_path.replace(".mp3", ".wav"))
        self.engine(
            text=text,
            output_file=audio_path_wav,
            voice_name=self.voice,
            speed=self.speed,
            lang=self.lang,
        )

        mp3_audio_path = str(Path(cache_dir) / audio_path)
        wav2mp3(audio_path_wav, mp3_audio_path)
        remove_bookmarks(audio_path_wav)

        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }
