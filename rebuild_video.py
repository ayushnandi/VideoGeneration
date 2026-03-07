"""
Rebuild video from existing audio files (skips TTS).
Uses only the first 15 dialogue lines since line_0015.mp3 is missing.
Extracts word-level timestamps using Whisper for accurate subtitle sync.
"""

import json
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import Config
from app.services.tts_service import get_audio_duration
from app.services.video_service import VideoService


def extract_word_timings_whisper(audio_path, model):
    """Use faster-whisper to get word-level timestamps from an audio file."""
    segments, _ = model.transcribe(
        audio_path,
        language="hi",
        word_timestamps=True,
    )
    word_timings = []
    for segment in segments:
        for word in segment.words:
            word_timings.append({
                "word": word.word.strip(),
                "start": word.start,
                "end": word.end,
            })
    return word_timings


def main():
    with open(Config.SPEAKERS_CONFIG, "r", encoding="utf-8") as f:
        speakers = json.load(f)

    with open(os.path.join(Config.ASSETS_DIR, "..", "demo_dialogue.json"), "r", encoding="utf-8") as f:
        dialogue = json.load(f)

    # Only use first 15 lines (we have audio for 0-14)
    dialogue = dialogue[:15]

    config = {
        "TEMP_DIR": Config.TEMP_DIR,
        "OUTPUT_DIR": Config.OUTPUT_DIR,
        "SPEAKERS": speakers,
        "SPEAKERS_DIR": Config.SPEAKERS_DIR,
        "FFMPEG_BIN": Config.FFMPEG_BIN,
        "FFPROBE_BIN": Config.FFPROBE_BIN,
        "BACKGROUND_VIDEO": Config.BACKGROUND_VIDEO,
        "VIDEO_WIDTH": Config.VIDEO_WIDTH,
        "VIDEO_HEIGHT": Config.VIDEO_HEIGHT,
        "OVERLAY_WIDTH": Config.OVERLAY_WIDTH,
        "OVERLAY_HEIGHT": Config.OVERLAY_HEIGHT,
        "ASSETS_DIR": Config.ASSETS_DIR,
        "FONT_PATH": Config.FONT_PATH,
        "FONT_NAME": Config.FONT_NAME,
        "SUBTITLE_FONT_SIZE": Config.SUBTITLE_FONT_SIZE,
        "SUBTITLE_HIGHLIGHT_EXTRA_SIZE": Config.SUBTITLE_HIGHLIGHT_EXTRA_SIZE,
        "SUBTITLE_WORDS_PER_CHUNK": Config.SUBTITLE_WORDS_PER_CHUNK,
    }

    os.makedirs(config["OUTPUT_DIR"], exist_ok=True)
    job_dir = os.path.join(config["TEMP_DIR"], "demo")
    ffmpeg = config["FFMPEG_BIN"]
    ffprobe = config["FFPROBE_BIN"]

    # Load Whisper model once for word-level alignment
    print("=== Loading Whisper model for word alignment ===")
    from faster_whisper import WhisperModel
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    print("  Model loaded.")

    # Phase 1: Get durations and word timings from existing audio
    print("\n=== Phase 1: Reading audio durations + word timings ===")
    segments = []
    for i in range(len(dialogue)):
        audio_path = os.path.join(job_dir, f"line_{i:04d}.mp3")
        if not os.path.exists(audio_path):
            print(f"ERROR: Missing {audio_path}")
            sys.exit(1)
        duration = get_audio_duration(audio_path, ffprobe)
        word_timings = extract_word_timings_whisper(audio_path, whisper_model)
        segments.append({"index": i, "path": audio_path, "duration": duration, "word_timings": word_timings})
        wt_count = len(word_timings)
        print(f"  [{i+1}/{len(dialogue)}] {duration:.2f}s ({wt_count} words) - {dialogue[i]['text'][:50]}...")

    # Phase 2: Timestamps with word-level alignment
    print("\n=== Phase 2: Calculating timestamps ===")
    timestamps = []
    current = 0.0
    for seg in segments:
        # Offset word timings to absolute time
        word_timings = []
        for wt in seg.get("word_timings", []):
            word_timings.append({
                "word": wt["word"],
                "start": current + wt["start"],
                "end": current + wt["end"],
            })
        timestamps.append({
            "start": current,
            "end": current + seg["duration"],
            "word_timings": word_timings,
        })
        current += seg["duration"]
    total_duration = timestamps[-1]["end"]
    print(f"  Total duration: {total_duration:.2f}s")

    # Phase 3: Concat audio
    print("\n=== Phase 3: Concatenating audio ===")
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

    # Phase 5: Composite with ASS karaoke subtitles
    print("\n=== Phase 5: Compositing video ===")
    output_path = os.path.join(config["OUTPUT_DIR"], "demo_output.mp4")

    service = VideoService(config)
    service._composite(bg_video, concat_audio, timestamps, dialogue, output_path)
    print(f"  -> {output_path}")

    print(f"\n=== DONE! ===")
    print(f"Output: {output_path}")
    print(f"Duration: {total_duration:.2f}s")


if __name__ == "__main__":
    main()
