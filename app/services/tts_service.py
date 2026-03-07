import base64
import subprocess
import time

import requests


def _extract_word_timings(text, alignment):
    """Convert character-level alignment data into word-level timings.

    Returns a list of {"word": str, "start": float, "end": float}.
    """
    if not alignment:
        return []

    characters = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    if not characters or len(characters) != len(starts) or len(characters) != len(ends):
        return []

    words = []
    current_word = ""
    word_start = None

    for ch, s, e in zip(characters, starts, ends):
        if ch == " ":
            if current_word:
                words.append({"word": current_word, "start": word_start, "end": last_end})
                current_word = ""
                word_start = None
        else:
            if word_start is None:
                word_start = s
            current_word += ch
            last_end = e

    if current_word:
        words.append({"word": current_word, "start": word_start, "end": last_end})

    return words


def generate_tts(text, voice_id, output_path, api_key, model, max_retries=3, ffprobe_bin="ffprobe"):
    """Call ElevenLabs TTS API with timestamps and save the audio file.

    Returns (duration, word_timings) where word_timings is a list of
    {"word": str, "start": float, "end": float}.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    for attempt in range(max_retries):
        resp = requests.post(url, json=payload, headers=headers, timeout=60)

        if resp.status_code == 200:
            data = resp.json()
            audio_b64 = data.get("audio_base64", "")
            alignment = data.get("alignment", {})

            with open(output_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))

            duration = get_audio_duration(output_path, ffprobe_bin)
            word_timings = _extract_word_timings(text, alignment)
            return duration, word_timings

        if resp.status_code == 429:
            wait = 2 ** (attempt + 1)
            time.sleep(wait)
            continue

        resp.raise_for_status()

    raise RuntimeError(f"TTS failed after {max_retries} retries (rate-limited)")


def get_audio_duration(filepath, ffprobe_bin="ffprobe"):
    """Use ffprobe to get duration of an audio file in seconds."""
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())
