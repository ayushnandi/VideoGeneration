"""Generate TTS audio files only — no video compositing."""
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from config.settings import Config

def main():
    # Load dialogue
    dialogue_path = os.path.join(Config.ASSETS_DIR, "..", "demo_dialogue.json")
    with open(dialogue_path, "r", encoding="utf-8") as f:
        dialogue = json.load(f)

    # Load speakers config
    with open(Config.SPEAKERS_CONFIG, "r", encoding="utf-8") as f:
        speakers = json.load(f)

    audio_dir = os.path.join("output", "audio")
    os.makedirs(audio_dir, exist_ok=True)

    from app.services.tts_service import generate_tts

    print(f"Generating TTS for {len(dialogue)} lines...\n")

    for i, line in enumerate(dialogue):
        speaker = line["speaker"].lower()
        speaker_cfg = speakers.get(speaker, speakers["default"])
        voice_id = speaker_cfg["voice_id"]

        audio_path = os.path.join(audio_dir, f"line_{i:04d}_{speaker}.mp3")
        print(f"  [{i+1}/{len(dialogue)}] {speaker}: {line['text'][:60]}...", flush=True)

        try:
            duration = generate_tts(
                line["text"], voice_id, audio_path,
                Config.ELEVENLABS_API_KEY, Config.ELEVENLABS_MODEL,
                ffprobe_bin=Config.FFPROBE_BIN
            )
            print(f"    -> {duration:.2f}s  ({audio_path})", flush=True)
        except Exception as e:
            print(f"    ERROR: {e}", flush=True)

    print(f"\nDone! Audio files saved in: {audio_dir}/")

if __name__ == "__main__":
    main()
