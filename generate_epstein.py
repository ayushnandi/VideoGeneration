"""
Generate Epstein documentary-style video with script images and background music.
Usage: python generate_epstein.py
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
        "text": "Tanmay, ek interesting sawaal… agar kisi ek insaan ke paas duniya ke sabse powerful logon ke secrets ho — Donald Trump, Bill Gates, Elon Musk, Prince Andrew jaise logon ke — toh kya woh insaan duniya ko control kar sakta hai?"
    },
    {
        "speaker": "tanmay",
        "text": "Yeh hi wajah hai ki Jeffrey Epstein ka naam itna controversial hai. Banda pehle ek simple maths teacher tha, college dropout. Lekin kuch hi saalon mein billionaires ka financial advisor ban gaya."
    },
    {
        "speaker": "tanmay",
        "text": "Private jets, New York ka 7-storey mansion, aur ek private island jahan powerful log parties ke liye aate the."
    },
    {
        "speaker": "samay",
        "text": "Lekin itni power ka source kya tha?"
    },
    {
        "speaker": "tanmay",
        "text": "Allegations ke according uske mansion aur island mein hidden cameras lage the — bedrooms tak record hote the."
    },
    {
        "speaker": "tanmay",
        "text": "Victims ne bola wahan vulgar parties aur minor exploitation hota tha."
    },
    {
        "speaker": "tanmay",
        "text": "FBI ko CDs mile jinke labels the Young girl plus powerful name."
    },
    {
        "speaker": "tanmay",
        "text": "Isi liye log bolte hain uska real business paisa nahi… secrets collect karna aur influence banana tha."
    },
    {
        "speaker": "samay",
        "text": "Aur jab Epstein Files release hui…"
    },
    {
        "speaker": "tanmay",
        "text": "Toh aur bhi powerful connections saamne aaye. Lekin sabse shocking twist — trial se pehle hi Epstein jail mein suicide kar gaya."
    },
    {
        "speaker": "samay",
        "text": "Aur wahi se sabse bada sawaal shuru hota hai…"
    },
    {
        "speaker": "tanmay",
        "text": "Kya woh sach mein suicide tha? Ya phir kisi ne hata diya us aadmi ko… jiske paas duniya ke sabse powerful logon ke raaz the?"
    },
]

# ── Image mapping: each dialogue line → list of images to show ──
# Images are displayed big, centered, above captions
# Format: (image_path, position) where position is "center" or ("top", "bottom") for dual
IMG_DIR = os.path.join(Config.TEMP_DIR, "epstein_images")

IMAGE_MAP = {
    # Line 0: "powerful logon ke secrets ho" - Modi meme for funny effect
    0: [os.path.join(IMG_DIR, "modi_meme.png")],
    # Line 1: Jeffrey Epstein intro - mugshot + mansion staircase
    1: [
        os.path.join(IMG_DIR, "epstein_mugshot.jpg"),
        os.path.join(IMG_DIR, "img_7bff.png"),
    ],
    # Line 2: Private jets, mansion, island
    2: [
        os.path.join(IMG_DIR, "img_26f5.png"),       # Epstein on private jet
        os.path.join(IMG_DIR, "img_7bff1.png"),       # mansion interior
        os.path.join(IMG_DIR, "epstein_island.jpg"),   # private island
    ],
    # Line 3: "power ka source kya tha?" - Epstein with powerful people
    3: [os.path.join(IMG_DIR, "img_85fc.png")],       # Clinton painting in mansion
    # Line 4: Hidden cameras - mansion room + Andrew photos
    4: [
        os.path.join(IMG_DIR, "img_8200.png"),         # mansion hidden camera photo
        os.path.join(IMG_DIR, "epstein_andrew.jpg"),   # Epstein-Andrew photos
    ],
    # Line 5: Vulgar parties, exploitation
    5: [
        os.path.join(IMG_DIR, "img_25e0.png"),         # pool scene
        os.path.join(IMG_DIR, "epstein_room.jpg"),     # room scene
    ],
    # Line 6: FBI CDs - FBI document
    6: [
        os.path.join(IMG_DIR, "img_32f6.png"),         # FBI redacted document
        os.path.join(IMG_DIR, "img_45c0.png"),         # another scene
    ],
    # Line 7: secrets collect karna - powerful people connections
    7: [
        os.path.join(IMG_DIR, "prince_andrew.jpg"),    # Prince Andrew
        os.path.join(IMG_DIR, "img_85fc.png"),         # Clinton painting
    ],
    # Line 8: "Epstein Files release hui" - FBI documents + Trump-Epstein
    8: [
        os.path.join(IMG_DIR, "img_32f6.png"),         # FBI redacted document
        os.path.join(IMG_DIR, "img_1795.png"),          # Trump with Epstein in background
    ],
    # Line 9: "shocking twist - jail mein suicide" - connections + jail cell
    9: [
        os.path.join(IMG_DIR, "img_1795.png"),          # Trump-Epstein powerful connections
        os.path.join(IMG_DIR, "images_1.jpg"),           # Epstein jail cell
    ],
    # Line 10: "sabse bada sawaal" - Epstein mugshot (dramatic)
    10: [os.path.join(IMG_DIR, "epstein_mugshot.jpg")],
    # Line 11: "Kya woh sach mein suicide tha?" - jail cell + island
    11: [
        os.path.join(IMG_DIR, "images_1.jpg"),           # jail cell
        os.path.join(IMG_DIR, "epstein_mugshot.jpg"),    # Epstein face
        os.path.join(IMG_DIR, "epstein_island.jpg"),     # his island empire
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

    job_dir = os.path.join(config["TEMP_DIR"], "epstein")
    os.makedirs(job_dir, exist_ok=True)

    # Validate
    if not config["ELEVENLABS_API_KEY"]:
        print("ERROR: Set ELEVENLABS_API_KEY in .env file")
        sys.exit(1)
    if not os.path.exists(config["BACKGROUND_VIDEO"]):
        print(f"ERROR: Background video not found at {config['BACKGROUND_VIDEO']}")
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

    # ── Phase 4: Prepare background ──
    print("\n=== Phase 4: Cropping background to 9:16 ===")
    bg_video = os.path.join(job_dir, "bg_loop.mp4")
    width = config["VIDEO_WIDTH"]
    height = config["VIDEO_HEIGHT"]

    # Use background1.webm starting from 7 minutes (420s)
    bg_src = os.path.join(config["ASSETS_DIR"], "backgrounds", "background1.webm")
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

    # ── Phase 5: Composite with speaker images + script images ──
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

    # ── Phase 7: Add background music ──
    print("\n=== Phase 7: Adding background music ===")
    output_path = os.path.join(config["OUTPUT_DIR"], "epstein_output.mp4")
    bg_music = os.path.join(config["ASSETS_DIR"], "bg-music",
                            "IcyBeast - 7 Weeks 3 Days.mp3")

    if os.path.exists(bg_music):
        cmd = [
            ffmpeg, "-y",
            "-i", sped_output,
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
    """Composite video with:
    - Speaker images (Samay/Tanmay) at bottom
    - Script-relevant images BIG at center-top above captions
    - ASS karaoke subtitles at middle
    """
    speakers = config["SPEAKERS"]
    speakers_dir = config["SPEAKERS_DIR"]
    vid_w = config["VIDEO_WIDTH"]
    vid_h = config["VIDEO_HEIGHT"]
    ffmpeg = config["FFMPEG_BIN"]
    default_ow = config["OVERLAY_WIDTH"]
    default_oh = config["OVERLAY_HEIGHT"]

    # ── Collect unique speaker images ──
    speaker_images = {}
    for line in dialogue:
        key = line["speaker"].lower()
        if key not in speaker_images:
            cfg = speakers.get(key, speakers["default"])
            speaker_images[key] = os.path.join(speakers_dir, cfg["image"])

    # ── Collect all unique script images ──
    all_script_images = []
    script_img_indices = {}  # path -> ffmpeg input index
    for line_idx, images in IMAGE_MAP.items():
        for img_path in images:
            if img_path not in script_img_indices:
                all_script_images.append(img_path)

    # ── Build FFmpeg inputs ──
    # 0 = bg video, 1 = audio, 2+ = speaker images, then script images
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

    # ── Build filter_complex ──
    filters = []

    # Scale speaker images
    margin = 30
    for key, idx in speaker_idx.items():
        cfg = speakers.get(key, speakers["default"])
        scale = cfg.get("scale", f"{default_ow}:{default_oh}")
        safe_key = key.replace(' ', '_')
        filters.append(f"[{idx}:v]scale={scale}[img_{safe_key}]")

    # Scale script images: big, centered above captions
    # Target: ~700px wide, maintain aspect ratio, max height ~500px
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

    # Overlay speakers (below middle at 58% height)
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

    # Overlay script images: centered horizontally, near top with padding
    # Position: centered at top, with 40px padding from top
    img_x = f"(W-overlay_w)/2"
    img_y_top = "40"        # single image at top
    img_y_upper = "30"      # dual: upper image
    img_y_lower = "340"     # dual: lower image (below first)

    for line_idx, images in IMAGE_MAP.items():
        if line_idx >= len(timestamps):
            continue

        line_start = timestamps[line_idx]["start"]
        line_end = timestamps[line_idx]["end"]
        line_dur = line_end - line_start

        if len(images) == 1:
            # Single image: show for entire line duration, centered at top
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
            # Two images: show first for first half, second for second half
            mid = line_start + line_dur / 2
            for img_i, img_path in enumerate(images):
                idx = script_img_indices[img_path]
                safe_label = f"simg_{idx}"
                out_label = f"v{overlay_counter}"
                if img_i == 0:
                    t_start, t_end = line_start, mid
                else:
                    t_start, t_end = mid, line_end
                filters.append(
                    f"[{prev}][{safe_label}]overlay={img_x}:{img_y_top}:"
                    f"enable='between(t,{t_start:.3f},{t_end:.3f})'[{out_label}]"
                )
                prev = out_label
                overlay_counter += 1

        elif len(images) >= 3:
            # Three+ images: split time equally
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

    # ── ASS karaoke subtitles ──
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

    # Write filter to script file
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

    # Cleanup temp files
    for tmp in (filter_script, ass_file):
        if os.path.exists(tmp):
            os.remove(tmp)

    if result.returncode != 0:
        raise RuntimeError(f"Compositing failed: {result.stderr}")


if __name__ == "__main__":
    main()
