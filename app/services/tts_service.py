import subprocess
import time

import requests


def generate_tts(text, voice_id, output_path, api_key, model, max_retries=3, ffprobe_bin="ffprobe"):
    """Call ElevenLabs TTS API and save the audio file. Returns duration in seconds."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    for attempt in range(max_retries):
        resp = requests.post(url, json=payload, headers=headers, timeout=60)

        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return get_audio_duration(output_path, ffprobe_bin)

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
