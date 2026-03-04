"""
Standalone demo script — generates a video directly without the Flask server.
Usage: python generate_demo.py
"""

import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
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

    # Build config dict (same shape as Flask app.config)
    config = {
        "TEMP_DIR": Config.TEMP_DIR,
        "OUTPUT_DIR": Config.OUTPUT_DIR,
        "SPEAKERS": speakers,
        "SPEAKERS_DIR": Config.SPEAKERS_DIR,
        "ELEVENLABS_API_KEY": Config.ELEVENLABS_API_KEY,
        "ELEVENLABS_MODEL": Config.ELEVENLABS_MODEL,
        "FFMPEG_BIN": Config.FFMPEG_BIN,
        "FFPROBE_BIN": Config.FFPROBE_BIN,
        "BACKGROUND_VIDEO": Config.BACKGROUND_VIDEO,
        "VIDEO_WIDTH": Config.VIDEO_WIDTH,
        "VIDEO_HEIGHT": Config.VIDEO_HEIGHT,
        "OVERLAY_WIDTH": Config.OVERLAY_WIDTH,
        "OVERLAY_HEIGHT": Config.OVERLAY_HEIGHT,
        "ASSETS_DIR": Config.ASSETS_DIR,
        "FONT_PATH": Config.FONT_PATH,
        "SUBTITLE_FONT_SIZE": Config.SUBTITLE_FONT_SIZE,
        "SUBTITLE_WORDS_PER_CHUNK": Config.SUBTITLE_WORDS_PER_CHUNK,
    }

    # Ensure dirs exist
    os.makedirs(config["TEMP_DIR"], exist_ok=True)
    os.makedirs(config["OUTPUT_DIR"], exist_ok=True)

    # Validate
    if not config["ELEVENLABS_API_KEY"]:
        print("ERROR: Set ELEVENLABS_API_KEY in .env file")
        sys.exit(1)

    if not os.path.exists(config["BACKGROUND_VIDEO"]):
        print(f"ERROR: Background video not found at {config['BACKGROUND_VIDEO']}")
        sys.exit(1)

    print(f"Dialogue: {len(dialogue)} lines")
    print(f"Video: {config['VIDEO_WIDTH']}x{config['VIDEO_HEIGHT']} (9:16 portrait)")
    print(f"FFmpeg: {config['FFMPEG_BIN']}")
    print()

    # Run pipeline synchronously (not threaded)
    from app.services.job_manager import job_manager
    from app.services.tts_service import generate_tts, get_audio_duration
    from app.services.video_service import VideoService

    job_id = "demo"
    job_dir = os.path.join(config["TEMP_DIR"], job_id)
    os.makedirs(job_dir, exist_ok=True)

    ffmpeg = config["FFMPEG_BIN"]
    ffprobe = config["FFPROBE_BIN"]

    # Phase 1: TTS
    print("=== Phase 1: Generating TTS audio ===")
    segments = []
    for i, line in enumerate(dialogue):
        speaker = line["speaker"].lower()
        speaker_cfg = speakers.get(speaker, speakers["default"])
        voice_id = speaker_cfg["voice_id"]

        audio_path = os.path.join(job_dir, f"line_{i:04d}.mp3")
        print(f"  [{i+1}/{len(dialogue)}] {speaker}: {line['text'][:50]}...")

        duration = generate_tts(
            line["text"], voice_id, audio_path,
            config["ELEVENLABS_API_KEY"], config["ELEVENLABS_MODEL"],
            ffprobe_bin=ffprobe
        )
        segments.append({"index": i, "path": audio_path, "duration": duration})
        print(f"    -> {duration:.2f}s")

    # Phase 2: Timestamps
    print("\n=== Phase 2: Calculating timestamps ===")
    timestamps = []
    current = 0.0
    for seg in segments:
        timestamps.append({"start": current, "end": current + seg["duration"]})
        current += seg["duration"]

    total_duration = timestamps[-1]["end"]
    print(f"  Total duration: {total_duration:.2f}s")

    for i, (ts, line) in enumerate(zip(timestamps, dialogue)):
        print(f"  [{ts['start']:.2f}s - {ts['end']:.2f}s] {line['speaker']}: {line['text'][:40]}...")

    # Phase 3: Concat audio
    print("\n=== Phase 3: Concatenating audio ===")
    import subprocess

    concat_audio = os.path.join(job_dir, "concat.wav")
    list_file = os.path.join(job_dir, "concat_list.txt")
    with open(list_file, "w") as f:
        for seg in segments:
            safe_path = seg["path"].replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
           "-ar", "44100", "-ac", "2", concat_audio]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  -> concat.wav ({total_duration:.2f}s)")

    # Phase 4: Prepare background
    print("\n=== Phase 4: Cropping background to 9:16 ===")
    bg_video = os.path.join(job_dir, "bg_loop.mp4")
    width = config["VIDEO_WIDTH"]
    height = config["VIDEO_HEIGHT"]

    cmd = [
        ffmpeg, "-y",
        "-stream_loop", "-1",
        "-i", config["BACKGROUND_VIDEO"],
        "-t", str(total_duration),
        "-vf", f"crop=in_h*9/16:in_h,scale={width}:{height}",
        "-an",
        "-c:v", "libx264", "-preset", "fast",
        bg_video,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  -> bg_loop.mp4 (9:16, {total_duration:.2f}s)")

    # Phase 5: Composite
    print("\n=== Phase 5: Compositing video ===")
    output_path = os.path.join(config["OUTPUT_DIR"], "demo_output.mp4")

    service = VideoService(config)
    service._composite(bg_video, concat_audio, timestamps, dialogue, output_path)
    print(f"  -> {output_path}")

    # Cleanup
    import shutil
    shutil.rmtree(job_dir, ignore_errors=True)

    print(f"\n=== DONE! ===")
    print(f"Output: {output_path}")
    print(f"Duration: {total_duration:.2f}s")


if __name__ == "__main__":
    main()
