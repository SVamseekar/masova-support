"""Bounded Gemini manager transcription and playable speech. Audio stays transient."""

from __future__ import annotations

import asyncio
import base64
import io
import os
import re
import wave
from typing import Any

from masova_agent.runtime.ops_llm import llm_api_key, ops_model_name

MAX_AUDIO_BYTES = 4 * 1024 * 1024
AUDIO_MIME_TYPES = frozenset(
    {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/mpeg",
        "audio/mp3",
        "audio/flac",
    }
)


async def _generate(**kwargs: Any) -> Any:
    from google import genai
    from google.genai import types

    key = llm_api_key()
    if not key:
        raise RuntimeError("speech_provider_not_configured")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000))
    try:
        return await asyncio.wait_for(client.aio.models.generate_content(**kwargs), timeout=45)
    finally:
        await client.aio.aclose()
        client.close()


async def transcribe_manager_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    from google.genai import types

    response = await _generate(
        model=ops_model_name(),
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    types.Part.from_text(
                        text="Transcribe the spoken request. Return only the transcript."
                    ),
                ],
            )
        ],
    )
    text = (response.text or "").strip()
    if not text or len(text) > 8000:
        raise RuntimeError("invalid_transcript")
    return text


def playable_audio(data: bytes, mime: str) -> dict[str, str]:
    """Gemini native speech is signed 16-bit mono PCM; wrap it in a WAV container."""
    if mime.startswith("audio/L16") or mime.startswith("audio/pcm"):
        match = re.search(r"rate=(\d+)", mime)
        rate = int(match.group(1)) if match else 24000
        if not 8000 <= rate <= 96000 or len(data) % 2:
            raise RuntimeError("invalid_pcm_audio")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(data)
        data, mime = output.getvalue(), "audio/wav"
    elif mime.split(";", 1)[0] not in AUDIO_MIME_TYPES:
        raise RuntimeError("unsupported_speech_format")
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise RuntimeError("invalid_speech_audio")
    return {"audioBase64": base64.b64encode(data).decode("ascii"), "mimeType": mime}


async def synthesize_manager_reply(text: str) -> dict[str, str]:
    from google.genai import types

    response = await _generate(
        model=os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        contents=text[:4000],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"),
                )
            ),
        ),
    )
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            inline = part.inline_data
            if inline and inline.data:
                return playable_audio(bytes(inline.data), inline.mime_type or "")
    raise RuntimeError("empty_speech_audio")
