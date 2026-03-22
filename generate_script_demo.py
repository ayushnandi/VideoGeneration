"""
Generate Dhurandhar video with script images and background music.
Usage: python generate_dhurandhar.py
"""

import json
import os
import subprocess
import sys
import shutil

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import Config
from app.services.tts_service import generate_tts, generate_fish_tts, get_audio_duration
from app.services.video_service import VideoService


# ── Script dialogue ──────────────────────────────────────────
DIALOGUE = [
    {
        "speaker": "samay",
        "text": "Ek sawaal… kya aap kisi aise insaan pe trust kar sakte ho… jo actually aapka dushman ho… par saalon tak aapke saath rehke aapka dost bana rahe?"
    },
    {
        "speaker": "tanmay",
        "text": "Yehi hai Dhurandhar ki real story. Film nahi… ek real undercover mission."
    },
    {
        "speaker": "tanmay",
        "text": "Indian Army officer Major Mohit Sharma, jo apni identity chhod kar Iftikhar Bhatt ban gaye… aur terrorists ke beech rehkar unka trust jeeta."
    },
    {
        "speaker": "samay",
        "text": "Matlab andar ghus ke pura system samajhna…"
    },
    {
        "speaker": "tanmay",
        "text": "Aur todna. Film mein Ranveer Singh unka role play kar rahe hain, aur R. Madhavan inspired hain Ajit Doval se — India ke real James Bond. Yeh sirf action nahi… mind game, patience aur sacrifice ki story hai."
    },
    {
        "speaker": "samay",
        "text": "Aur Part 2?"
    },
    {
        "speaker": "tanmay",
        "text": "Part 2 sirf continuation nahi hai… exposure hai. Un missions ka… jo kabhi officially bataye hi nahi gaye. Un connections ka… jo abhi bhi hidden hain."
    },
    {
        "speaker": "samay",
        "text": "Matlab story khatam nahi hui?"
    },
    {
        "speaker": "tanmay",
        "text": "Bilkul nahi… asli sawaal ab shuru hote hain— kya Mohit Sharma jaise aur agents aaj bhi kahin undercover hain?"
    },
    {
        "speaker": "tanmay",
        "text": "kya aise missions abhi bhi chal rahe hain… jinke baare mein humein kuch pata hi nahi? aur Dhurandhar Part 2… kya sirf film hai… ya ek aisi sachchai ka hissa… jo abhi bhi puri tarah saamne nahi aayi?"
    },
]

# ── Image mapping ──
IMG_DIR = os.path.join(Config.TEMP_DIR, "dhurandhar_images")

IMAGE_MAP = {
    # Line 0: "trust kar sakte ho... dushman ho" - Ranveer intense undercover shot
    0: [os.path.join(IMG_DIR, "image1.png")],
    # Line 1: "Dhurandhar ki real story" - full cast poster
    1: [os.path.join(IMG_DIR, "screenshot.png")],
    # Line 2: "Major Mohit Sharma... Iftikhar Bhatt" - Ranveer vs real Mohit Sharma
    2: [
        os.path.join(IMG_DIR, "article2.png"),      # Ranveer as undercover vs real Mohit Sharma
        os.path.join(IMG_DIR, "mohit_sharma.png"),   # movie vs real side-by-side
    ],
    # Line 3: "andar ghus ke pura system samajhna" - Ranveer as Iftikhar Bhatt comparison
    3: [os.path.join(IMG_DIR, "article1.png")],      # Ranveer vs real Major
    # Line 4: "Ranveer Singh... R. Madhavan... Ajit Doval" - actors + Doval
    4: [
        os.path.join(IMG_DIR, "arjun.png"),          # Ranveer close-up with Headley
        os.path.join(IMG_DIR, "madhavan.png"),        # Madhavan as Ajit Doval
        os.path.join(IMG_DIR, "akshaye.png"),         # Akshaye Khanna character
    ],
    # Line 5: "Aur Part 2?" - Sanjay Dutt comparison
    5: [os.path.join(IMG_DIR, "aslam_khan.png")],
    # Line 6: "exposure hai... hidden connections" - Sanjay scene + cast
    6: [
        os.path.join(IMG_DIR, "sanjay.png"),          # Sanjay Dutt character
        os.path.join(IMG_DIR, "screenshot.png"),      # full cast
    ],
    # Line 7: "story khatam nahi hui?" - intense Ranveer
    7: [os.path.join(IMG_DIR, "image1.png")],
    # Line 8: "Mohit Sharma jaise agents undercover hain?" - real vs movie
    8: [
        os.path.join(IMG_DIR, "mohit_sharma.png"),
        os.path.join(IMG_DIR, "article2.png"),
    ],
    # Line 9: "Dhurandhar Part 2... sachchai saamne nahi aayi" - dramatic ending
    9: [
        os.path.join(IMG_DIR, "arjun.png"),
        os.path.join(IMG_DIR, "screenshot.png"),
    ],
}


def main():
    with open(Config.SPEAKERS_CONFIG, "r", encoding="utf-8") as f:
        speakers = json.load(f)

    config = {
        "TEMP_DIR": Config.TEMP_DIR,
        "OUTPUT_DIR": Config.OUTPUT_DIR,
        "SPEAKERS": speakers,
        "SPEAKERS_DIR": Config.SPEAKERS_DIR,
        "ELEVENLABS_API_KEY": Config.ELEVENLABS_API_KEY,
        "ELEVENLABS_MODEL": Config.ELEVENLABS_MODEL,
        "FISH_AUDIO_API_KEY": Config.FISH_AUDIO_API_KEY,
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

    os.makedirs(config["TEMP_DIR"], exist_ok=True)
    os.makedirs(config["OUTPUT_DIR"], exist_ok=True)

    dialogue = DIALOGUE
    ffmpeg = config["FFMPEG_BIN"]
    ffprobe = config["FFPROBE_BIN"]

    job_dir = os.path.join(config["TEMP_DIR"], "dhurandhar")
    os.makedirs(job_dir, exist_ok=True)

    if not config["ELEVENLABS_API_KEY"]:
        print("ERROR: Set ELEVENLABS_API_KEY in .env file")
        sys.exit(1)

    bg_src = os.path.join(config["ASSETS_DIR"], "backgrounds", "background1.webm")
    if not os.path.exists(bg_src):
        print(f"ERROR: Background video not found at {bg_src}")
        sys.exit(1)

    print(f"Dialogue: {len(dialogue)} lines")
    print(f"Video: {config['VIDEO_WIDTH']}x{config['VIDEO_HEIGHT']} (9:16 portrait)")
    print()

    # ── Phase 1: TTS ──
    print("=== Phase 1: Generating TTS audio ===")
    segments = []
    for i, line in enumerate(dialogue):
        speaker = line["speaker"].lower()
        speaker_cfg = speakers.get(speaker, speakers["default"])
        voice_id = speaker_cfg["voice_id"]
        tts_provider = speaker_cfg.get("tts_provider", "elevenlabs")

        audio_path = os.path.join(job_dir, f"line_{i:04d}.mp3")
        print(f"  [{i+1}/{len(dialogue)}] {speaker} ({tts_provider}): {line['text'][:60]}...")

        if tts_provider == "fish":
            duration, word_timings = generate_fish_tts(
                line["text"], voice_id, audio_path,
                config["FISH_AUDIO_API_KEY"], ffprobe_bin=ffprobe
            )
        else:
            duration, word_timings = generate_tts(
                line["text"], voice_id, audio_path,
                config["ELEVENLABS_API_KEY"], config["ELEVENLABS_MODEL"],
                ffprobe_bin=ffprobe
            )
        segments.append({"index": i, "path": audio_path, "duration": duration, "word_timings": word_timings})
        print(f"    -> {duration:.2f}s ({len(word_timings)} word timings)")

    # ── Phase 2: Timestamps ──
    print("\n=== Phase 2: Calculating timestamps ===")
    timestamps = []
    current = 0.0
    for seg in segments:
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

    for i, (ts, line) in enumerate(zip(timestamps, dialogue)):
        print(f"  [{ts['start']:.2f}s - {ts['end']:.2f}s] {line['speaker']}: {line['text'][:50]}...")

    # ── Phase 3: Concat audio ──
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

    # ── Phase 4: Prepare background from background1.webm at 7min ──
    print("\n=== Phase 4: Cropping background to 9:16 (from 7:00) ===")
    bg_video = os.path.join(job_dir, "bg_loop.mp4")
    width = config["VIDEO_WIDTH"]
    height = config["VIDEO_HEIGHT"]
    bg_start = 420  # 7 minutes

    cmd = [
        ffmpeg, "-y",
        "-ss", str(bg_start),
        "-stream_loop", "-1",
        "-i", bg_src,
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

    # ── Phase 5: Composite ──
    print("\n=== Phase 5: Compositing video with script images ===")
    raw_output = os.path.join(job_dir, "raw_output.mp4")
    _composite_with_images(config, bg_video, concat_audio, timestamps, dialogue, raw_output)
    print(f"  -> raw_output.mp4")

    # ── Phase 6: Speed up 1.2x ──
    print("\n=== Phase 6: Speeding up 1.2x ===")
    sped_output = os.path.join(job_dir, "sped_output.mp4")
    speed = 1.2
    sped_duration = total_duration / speed

    cmd = [
        ffmpeg, "-y",
        "-i", raw_output,
        "-filter_complex",
        f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        sped_output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  -> sped_output.mp4 (1.2x, {sped_duration:.2f}s)")

    # ── Phase 7: Add background music from 1:01 ──
    print("\n=== Phase 7: Adding background music (from 1:01) ===")
    output_path = os.path.join(config["OUTPUT_DIR"], "dhurandhar_output.mp4")
    bg_music = os.path.join(config["ASSETS_DIR"], "bg-music",
                            "Ishq Jalakar - Karvaan _ Dhurandhar _ Ranveer Singh, Shashwat Sachdev, Aditya Dhar.mp3")

    if os.path.exists(bg_music):
        cmd = [
            ffmpeg, "-y",
            "-i", sped_output,
            "-ss", "61",   # start from 1:01
            "-stream_loop", "-1",
            "-i", bg_music,
            "-filter_complex",
            f"[1:a]volume=0.36[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-t", f"{sped_duration:.3f}",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        print(f"  WARNING: BG music not found at {bg_music}, skipping")
        cmd = [ffmpeg, "-y", "-i", sped_output, "-c", "copy", output_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  -> {output_path}")

    # Cleanup
    shutil.rmtree(job_dir, ignore_errors=True)

    print(f"\n=== DONE! ===")
    print(f"Output: {output_path}")
    print(f"Duration: {sped_duration:.2f}s (original {total_duration:.2f}s @ {speed}x)")


def _composite_with_images(config, bg_video, audio, timestamps, dialogue, output_path):
    """Composite video with speaker images, script images, and ASS subtitles."""
    speakers = config["SPEAKERS"]
    speakers_dir = config["SPEAKERS_DIR"]
    vid_w = config["VIDEO_WIDTH"]
    vid_h = config["VIDEO_HEIGHT"]
    ffmpeg = config["FFMPEG_BIN"]
    default_ow = config["OVERLAY_WIDTH"]
    default_oh = config["OVERLAY_HEIGHT"]

    speaker_images = {}
    for line in dialogue:
        key = line["speaker"].lower()
        if key not in speaker_images:
            cfg = speakers.get(key, speakers["default"])
            speaker_images[key] = os.path.join(speakers_dir, cfg["image"])

    all_script_images = []
    script_img_indices = {}
    for line_idx, images in IMAGE_MAP.items():
        for img_path in images:
            if img_path not in script_img_indices:
                all_script_images.append(img_path)

    inputs = ["-i", bg_video, "-i", audio]
    next_idx = 2

    speaker_idx = {}
    for key, img_path in speaker_images.items():
        inputs.extend(["-loop", "1", "-i", img_path])
        speaker_idx[key] = next_idx
        next_idx += 1

    for img_path in all_script_images:
        inputs.extend(["-loop", "1", "-i", img_path])
        script_img_indices[img_path] = next_idx
        next_idx += 1

    filters = []
    margin = 30

    for key, idx in speaker_idx.items():
        cfg = speakers.get(key, speakers["default"])
        scale = cfg.get("scale", f"{default_ow}:{default_oh}")
        safe_key = key.replace(' ', '_')
        filters.append(f"[{idx}:v]scale={scale}[img_{safe_key}]")

    script_img_w = 700
    script_img_h = 500
    for img_path, idx in script_img_indices.items():
        safe_label = f"simg_{idx}"
        filters.append(
            f"[{idx}:v]scale={script_img_w}:{script_img_h}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={script_img_w}:{script_img_h}:(ow-iw)/2:(oh-ih)/2:color=black@0"
            f"[{safe_label}]"
        )

    prev = "0:v"
    overlay_counter = 0
    for key, idx in speaker_idx.items():
        cfg = speakers.get(key, speakers["default"])
        position = cfg.get("position", "right")
        safe_key = key.replace(' ', '_')

        if position == "center-left":
            x_expr = f"(W*30/100)-(overlay_w/2)"
        elif position == "center-right":
            x_expr = f"(W*70/100)-(overlay_w/2)"
        elif position == "left":
            x_expr = str(margin)
        else:
            x_expr = f"W-overlay_w-{margin}"

        y_expr = f"(H*58/100)-(overlay_h/2)"

        windows = []
        for i, line in enumerate(dialogue):
            if line["speaker"].lower() == key:
                windows.append(
                    f"between(t,{timestamps[i]['start']:.3f},{timestamps[i]['end']:.3f})"
                )
        if not windows:
            continue

        enable_expr = "+".join(windows)
        out_label = f"v{overlay_counter}"
        filters.append(
            f"[{prev}][img_{safe_key}]overlay={x_expr}:{y_expr}:"
            f"enable='{enable_expr}'[{out_label}]"
        )
        prev = out_label
        overlay_counter += 1

    img_x = f"(W-overlay_w)/2"
    img_y_top = "40"

    for line_idx, images in IMAGE_MAP.items():
        if line_idx >= len(timestamps):
            continue

        line_start = timestamps[line_idx]["start"]
        line_end = timestamps[line_idx]["end"]
        line_dur = line_end - line_start

        if len(images) == 1:
            idx = script_img_indices[images[0]]
            safe_label = f"simg_{idx}"
            out_label = f"v{overlay_counter}"
            filters.append(
                f"[{prev}][{safe_label}]overlay={img_x}:{img_y_top}:"
                f"enable='between(t,{line_start:.3f},{line_end:.3f})'[{out_label}]"
            )
            prev = out_label
            overlay_counter += 1
        elif len(images) == 2:
            mid = line_start + line_dur / 2
            for img_i, img_path in enumerate(images):
                idx = script_img_indices[img_path]
                safe_label = f"simg_{idx}"
                out_label = f"v{overlay_counter}"
                t_start = line_start if img_i == 0 else mid
                t_end = mid if img_i == 0 else line_end
                filters.append(
                    f"[{prev}][{safe_label}]overlay={img_x}:{img_y_top}:"
                    f"enable='between(t,{t_start:.3f},{t_end:.3f})'[{out_label}]"
                )
                prev = out_label
                overlay_counter += 1
        elif len(images) >= 3:
            chunk_dur = line_dur / len(images)
            for img_i, img_path in enumerate(images):
                idx = script_img_indices[img_path]
                safe_label = f"simg_{idx}"
                out_label = f"v{overlay_counter}"
                t_start = line_start + img_i * chunk_dur
                t_end = line_start + (img_i + 1) * chunk_dur
                filters.append(
                    f"[{prev}][{safe_label}]overlay={img_x}:{img_y_top}:"
                    f"enable='between(t,{t_start:.3f},{t_end:.3f})'[{out_label}]"
                )
                prev = out_label
                overlay_counter += 1

    service = VideoService(config)
    ass_file = output_path + ".ass"
    fonts_dir = os.path.join(config["ASSETS_DIR"], "fonts")
    service._generate_ass_file(timestamps, dialogue, ass_file)

    ass_path_ff = ass_file.replace("\\", "/").replace(":", "\\:")
    fonts_dir_ff = fonts_dir.replace("\\", "/").replace(":", "\\:")

    filters.append(
        f"[{prev}]ass='{ass_path_ff}':fontsdir='{fonts_dir_ff}'[final]"
    )

    filter_complex = ";".join(filters)

    filter_script = output_path + ".filtergraph.txt"
    with open(filter_script, "w", encoding="utf-8") as f:
        f.write(filter_complex)

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex_script", filter_script,
        "-map", "[final]",
        "-map", "1:a",
        "-t", f"{timestamps[-1]['end']:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    for tmp in (filter_script, ass_file):
        if os.path.exists(tmp):
            os.remove(tmp)

    if result.returncode != 0:
        raise RuntimeError(f"Compositing failed: {result.stderr}")


if __name__ == "__main__":
    main()
