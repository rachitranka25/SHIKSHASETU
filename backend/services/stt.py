"""Speech-to-Text service."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class WhisperSTTService:
    def __init__(self):
        logger.info("[STT] Initializing Whisper STT (Mock/Fallback)")

    async def transcribe_async(self, audio_path: str, language: Optional[str] = None) -> dict:
        """Mock transcription for now."""
        return {
            "text": "This is a transcribed voice message. The STT model is currently initializing in the background. Please try typing your message for now.",
            "language": language or "en",
            "confidence": 0.9,
        }

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        """Mock transcription for now."""
        return {
            "text": "This is a transcribed voice message. The STT model is currently initializing in the background. Please try typing your message for now.",
            "language": language or "en",
            "confidence": 0.9,
        }

_stt_instance = None

def get_whisper_service():
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = WhisperSTTService()
    return _stt_instance
