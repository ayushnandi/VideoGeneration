"""
End-to-end: Generate AIB-style video with sound effects + meme overlays,
then auto-distribute to all platforms.

Usage: python generate_and_post.py
"""

import json
import os
import shutil
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from config.settings import Config

# ── Sound effects to layer at strategic moments ──────────────────────
# Timestamps are in "sped-up" time (after 1.2x speed).
# They'll be calculated dynamically after we know segment durations.
# Instead, we define them as fractional positions (0.0-1.0) of total duration,
# plus some fixed offsets after specific dialogue lines.
SOUND_EFFECTS_AFTER_LINE = {
    # line_index: [{"file": "...", "volume": float}]
    0:  [{"file": "vine-boom-sound-effect_KT89XIq.mp3", "volume": 0.15}],  # LPG tension intro
    3:  [{"file": "bruhh.mp3", "volume": 0.18}],               # "monopoly khatam hogi"
    5:  [{"file": "vine-boom-sound-effect_KT89XIq.mp3", "volume": 0.15}],  # "gas bhi rahegi, electricity bhi"
}

# ── Cat/meme image overlays at reaction moments ─────────────────────
CAT_OVERLAYS_AFTER_LINE = {
    1:  {"image": "cat_realization_ooh.jpg", "duration": 1.5},       # "habits change hoti hain"
    5:  {"image": "cat_innocent_idle.png", "duration": 1.3},         # "gas bhi rahegi"
}

# ── Reference images shown during relevant dialogue ──────────────────
# Shown at center/opposite side of speaker, ~300px wide
REFERENCE_OVERLAYS = {
    # line_index: image_path — shown for the entire line duration
    0: os.path.join(Config.ASSETS_DIR, "ref_cooktop.png"),  # LPG/induction talk
    3: os.path.join(Config.ASSETS_DIR, "ref_induction.png"),  # piped gas, induction options
    4: os.path.join(Config.ASSETS_DIR, "ref_cooktop.png"),  # lifestyle change
    5: os.path.join(Config.ASSETS_DIR, "ref_induction.png"),  # alternatives, future kitchen
}

# ── Platform captions (hardcoded, no OpenAI) ─────────────────────────
TITLE = "Samay Raina x Tanmay Bhatt - Indian Kitchen Ka Future"

CAPTIONS = {
    "youtube": {
        "title": "Samay Raina x Tanmay Bhatt - LPG Crisis & Indian Kitchen Ka Future",
        "description": (
            "Samay Raina and Tanmay Bhatt discuss the LPG cylinder price crisis, "
            "the shift to induction cooking, and how Indian kitchens are evolving.\n\n"
            "Topics covered:\n"
            "- LPG cylinder supply and price tensions\n"
            "- Why cities are shifting to induction stoves\n"
            "- Piped gas, electric cooking, and the end of LPG monopoly\n"
            "- The future of Indian kitchen energy\n\n"
            "#SamayRaina #TanmayBhatt #LPG #InductionCooking #IndianKitchen "
            "#GasCylinder #IndiaNews #IndianCreators "
            "#IndiaGotLatent #maisamayhoon #tanmaybhat"
        ),
        "tags": [
            "Samay Raina", "Tanmay Bhatt", "LPG", "Gas Cylinder",
            "Induction Cooking", "Indian Kitchen", "India News",
            "Piped Gas", "Electric Cooking", "Indian Creators",
            "India's Got Latent", "maisamayhoon", "tanmaybhat",
        ],
    },
    "instagram": (
        "LPG cylinder ki price badh rahi hai, supply unstable hai\n"
        "Cities me log induction pe shift kar rahe hain\n"
        "Indian kitchen ka future ek fuel pe depend nahi rahega \U0001f525\n\n"
        "@maisamayhoon @tanmaybhat @indiasgotlatent\n\n"
        "#LPG #GasCylinder #InductionCooking #IndianKitchen #IndiaNews "
        "#SamayRaina #TanmayBhatt #Trending #Viral #IndiaGotLatent"
    ),
    "facebook": (
        "LPG cylinder ki prices aur supply ko leke kya hone wala hai? \U0001f525\n\n"
        "Samay aur Tanmay discuss karte hain ki Indian kitchens kaise change ho rahe hain - "
        "induction stoves, piped gas, electric cooking. Future me ek hi fuel pe "
        "depend nahi rahega \U0001f3ac\n\n"
        "@maisamayhoon @tanmaybhat @indiasgotlatent"
    ),
    "linkedin": (
        "The Future of Indian Kitchen Energy\n\n"
        "Key insights from Samay Raina & Tanmay Bhatt's conversation:\n\n"
        "\u2022 LPG supply instability and price increases are driving behavioral change\n"
        "\u2022 Urban consumers are adopting induction and electric cooking alternatives\n"
        "\u2022 Crisis drives habit change - similar to WFH adoption during COVID\n"
        "\u2022 The future Indian kitchen won't depend on a single fuel source\n\n"
        "Energy transitions happen when supply becomes unreliable and alternatives become accessible.\n\n"
        "#Energy #IndianKitchen #LPG #InductionCooking #ConsumerBehavior #IndiaGotLatent"
    ),
}


def main():
    # ── Load dialogue ────────────────────────────────────────────────
    dialogue_path = os.path.join(os.path.dirname(__file__), "aib_dialogue.json")
    with open(dialogue_path, "r", encoding="utf-8") as f:
        dialogue = json.load(f)

    # ── Load speakers config ─────────────────────────────────────────
    with open(Config.SPEAKERS_CONFIG, "r", encoding="utf-8") as f:
        speakers = json.load(f)

    # ── Build config dict ────────────────────────────────────────────
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
        "BACKGROUND_VIDEO": os.path.join(Config.BACKGROUNDS_DIR, "background1.webm"),
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

    # ── Validate ─────────────────────────────────────────────────────
    providers_used = set()
    for line in dialogue:
        key = line["speaker"].lower()
        cfg = speakers.get(key, speakers["default"])
        providers_used.add(cfg.get("tts_provider", "elevenlabs"))

    if "elevenlabs" in providers_used and not config["ELEVENLABS_API_KEY"]:
        print("ERROR: Set ELEVENLABS_API_KEY in .env file")
        sys.exit(1)
    if "fish" in providers_used and not config["FISH_AUDIO_API_KEY"]:
        print("ERROR: Set FISH_AUDIO_API_KEY in .env file")
        sys.exit(1)

    bg_video_src = config["BACKGROUND_VIDEO"]
    if not os.path.exists(bg_video_src):
        # Fallback to background.mp4
        bg_video_src = os.path.join(Config.BACKGROUNDS_DIR, "background.mp4")
        config["BACKGROUND_VIDEO"] = bg_video_src
        if not os.path.exists(bg_video_src):
            print(f"ERROR: No background video found")
            sys.exit(1)
        print(f"  NOTE: background1.webm not found, using background.mp4")

    print("=" * 60)
    print("  AIB VIDEO GENERATION + AUTO-DISTRIBUTION")
    print("=" * 60)
    print(f"  Dialogue: {len(dialogue)} lines")
    print(f"  Video:    {config['VIDEO_WIDTH']}x{config['VIDEO_HEIGHT']} (9:16)")
    print(f"  Background: {os.path.basename(bg_video_src)}")
    print(f"  Sound FX: {len(SOUND_EFFECTS_AFTER_LINE)} trigger points")
    print(f"  Cat overlays: {len(CAT_OVERLAYS_AFTER_LINE)} reaction moments")
    print("=" * 60)
    print()

    from app.services.job_manager import job_manager
    from app.services.tts_service import generate_tts, generate_fish_tts, get_audio_duration
    from app.services.video_service import VideoService

    job_id = "aib_video"
    job_dir = os.path.join(config["TEMP_DIR"], job_id)
    os.makedirs(job_dir, exist_ok=True)

    ffmpeg = config["FFMPEG_BIN"]
    ffprobe = config["FFPROBE_BIN"]
    sfx_dir = os.path.join(config["ASSETS_DIR"], "memeReference")
    cat_dir = os.path.join(config["ASSETS_DIR"], "speakers", "cat")

    # ═════════════════════════════════════════════════════════════════
    # Phase 1: TTS Generation
    # ═════════════════════════════════════════════════════════════════
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
                config["FISH_AUDIO_API_KEY"], ffprobe_bin=ffprobe,
            )
        else:
            duration, word_timings = generate_tts(
                line["text"], voice_id, audio_path,
                config["ELEVENLABS_API_KEY"], config["ELEVENLABS_MODEL"],
                ffprobe_bin=ffprobe,
            )
        segments.append({"index": i, "path": audio_path, "duration": duration, "word_timings": word_timings})
        print(f"    -> {duration:.2f}s ({len(word_timings)} word timings)")

    # ═════════════════════════════════════════════════════════════════
    # Phase 2: Timestamp Calculation
    # ═════════════════════════════════════════════════════════════════
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

    # ═════════════════════════════════════════════════════════════════
    # Phase 3: Audio Concatenation
    # ═════════════════════════════════════════════════════════════════
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

    # ═════════════════════════════════════════════════════════════════
    # Phase 4: Background Preparation
    # ═════════════════════════════════════════════════════════════════
    print("\n=== Phase 4: Cropping background to 9:16 ===")
    bg_video = os.path.join(job_dir, "bg_loop.mp4")
    width = config["VIDEO_WIDTH"]
    height = config["VIDEO_HEIGHT"]

    cmd = [
        ffmpeg, "-y",
        "-ss", "300",
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

    # ═════════════════════════════════════════════════════════════════
    # Phase 5: Compositing (speakers + subtitles + cat overlays)
    # ═════════════════════════════════════════════════════════════════
    print("\n=== Phase 5: Compositing video with cat overlays ===")
    raw_output = os.path.join(job_dir, "raw_output.mp4")

    # Build cat overlay data for the composite step
    cat_overlays = []
    for line_idx, cat_cfg in CAT_OVERLAYS_AFTER_LINE.items():
        if line_idx < len(timestamps):
            start_time = timestamps[line_idx]["end"] - 0.3
            end_time = start_time + cat_cfg["duration"]
            if end_time > total_duration:
                end_time = total_duration
            cat_overlays.append({
                "image": os.path.join(cat_dir, cat_cfg["image"]),
                "start": start_time,
                "end": end_time,
            })

    # Build reference image overlays (shown during entire line, opposite to speaker)
    ref_overlays = []
    for line_idx, img_path in REFERENCE_OVERLAYS.items():
        if line_idx < len(timestamps) and os.path.exists(img_path):
            speaker_key = dialogue[line_idx]["speaker"].lower()
            speaker_cfg = speakers.get(speaker_key, speakers["default"])
            position = speaker_cfg.get("position", "right")
            # Place ref image on opposite side of speaker
            if position in ("center-left", "left"):
                ref_x = f"(W*65/100)-(overlay_w/2)"
            else:
                ref_x = f"(W*35/100)-(overlay_w/2)"
            ref_overlays.append({
                "image": img_path,
                "start": timestamps[line_idx]["start"],
                "end": timestamps[line_idx]["end"],
                "x_expr": ref_x,
            })

    _composite_with_cats(
        config, bg_video, concat_audio, timestamps, dialogue, raw_output,
        cat_overlays, ref_overlays
    )
    print(f"  -> raw_output.mp4")

    # ═════════════════════════════════════════════════════════════════
    # Phase 6: Speed up 1.2x
    # ═════════════════════════════════════════════════════════════════
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

    # Adjust timestamps for speed
    sped_timestamps = []
    for ts in timestamps:
        sped_timestamps.append({
            "start": ts["start"] / speed,
            "end": ts["end"] / speed,
        })

    # ═════════════════════════════════════════════════════════════════
    # Phase 7: Background Music
    # ═════════════════════════════════════════════════════════════════
    print("\n=== Phase 7: Adding background music ===")
    music_output = os.path.join(job_dir, "music_output.mp4")
    bg_music = os.path.join(config["ASSETS_DIR"], "bg-music", "Memory Reboot.mp3")

    if os.path.exists(bg_music):
        cmd = [
            ffmpeg, "-y",
            "-i", sped_output,
            "-stream_loop", "-1",
            "-i", bg_music,
            "-filter_complex",
            f"[1:a]volume=0.12[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-t", f"{sped_duration:.3f}",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            music_output,
        ]
    else:
        print(f"  WARNING: BG music not found, skipping")
        cmd = [ffmpeg, "-y", "-i", sped_output, "-c", "copy", music_output]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  -> music_output.mp4")

    # ═════════════════════════════════════════════════════════════════
    # Phase 7.5: Sound Effects
    # ═════════════════════════════════════════════════════════════════
    print("\n=== Phase 7.5: Mixing in sound effects ===")
    output_path = os.path.join(config["OUTPUT_DIR"], "aib_output.mp4")

    # Build list of SFX with absolute timestamps (sped-up time)
    sfx_entries = []
    for line_idx, effects in SOUND_EFFECTS_AFTER_LINE.items():
        if line_idx < len(sped_timestamps):
            trigger_time = sped_timestamps[line_idx]["end"] - 0.2
            for fx in effects:
                sfx_path = os.path.join(sfx_dir, fx["file"])
                if os.path.exists(sfx_path):
                    sfx_entries.append({
                        "path": sfx_path,
                        "timestamp": max(0, trigger_time),
                        "volume": fx["volume"],
                    })
                else:
                    print(f"  WARNING: SFX not found: {fx['file']}")

    if sfx_entries:
        _mix_sound_effects(ffmpeg, music_output, sfx_entries, sped_duration, output_path)
    else:
        print("  No sound effects to mix, copying as-is")
        cmd = [ffmpeg, "-y", "-i", music_output, "-c", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}")
            sys.exit(1)

    print(f"  -> {output_path}")

    # ── Cleanup temp ─────────────────────────────────────────────────
    shutil.rmtree(job_dir, ignore_errors=True)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n{'=' * 60}")
    print(f"  VIDEO COMPLETE!")
    print(f"  Output:   {output_path}")
    print(f"  Size:     {file_size_mb:.1f} MB")
    print(f"  Duration: {sped_duration:.2f}s (original {total_duration:.2f}s @ {speed}x)")
    print(f"{'=' * 60}")

    # ═════════════════════════════════════════════════════════════════
    # Phase 8: Auto-Distribute to All Platforms
    # ═════════════════════════════════════════════════════════════════
    print("\n=== Phase 8: Auto-distributing to all platforms ===")
    _distribute(output_path)

    print(f"\n{'=' * 60}")
    print(f"  ALL DONE! Video generated and distributed.")
    print(f"{'=' * 60}")


def _composite_with_cats(config, bg_video, audio, timestamps, dialogue, output_path, cat_overlays, ref_overlays=None):
    """Composite video with speaker images, subtitles, cat overlays, and reference images."""
    from app.services.video_service import VideoService

    if ref_overlays is None:
        ref_overlays = []

    speakers = config["SPEAKERS"]
    speakers_dir = config["SPEAKERS_DIR"]
    vid_w = config["VIDEO_WIDTH"]
    vid_h = config["VIDEO_HEIGHT"]
    default_ow = config["OVERLAY_WIDTH"]
    default_oh = config["OVERLAY_HEIGHT"]
    ffmpeg = config["FFMPEG_BIN"]

    margin = 30

    # Collect unique speakers and images
    speaker_images = {}
    for line in dialogue:
        key = line["speaker"].lower()
        if key not in speaker_images:
            cfg = speakers.get(key, speakers["default"])
            speaker_images[key] = os.path.join(speakers_dir, cfg["image"])

    # Build FFmpeg inputs: 0=bg, 1=audio, 2+=speaker images, then cat images, then ref images
    inputs = ["-i", bg_video, "-i", audio]
    speaker_idx = {}
    next_idx = 2
    for key, img_path in speaker_images.items():
        inputs.extend(["-loop", "1", "-i", img_path])
        speaker_idx[key] = next_idx
        next_idx += 1

    cat_input_indices = []
    for cat in cat_overlays:
        if os.path.exists(cat["image"]):
            inputs.extend(["-loop", "1", "-i", cat["image"]])
            cat_input_indices.append(next_idx)
            next_idx += 1
        else:
            cat_input_indices.append(None)
            print(f"  WARNING: Cat image not found: {cat['image']}")

    ref_input_indices = []
    for ref in ref_overlays:
        inputs.extend(["-loop", "1", "-i", ref["image"]])
        ref_input_indices.append(next_idx)
        next_idx += 1

    # Build filter_complex
    filters = []
    total_duration = timestamps[-1]["end"] if timestamps else 0

    # Scale speaker images
    for key, idx in speaker_idx.items():
        cfg = speakers.get(key, speakers["default"])
        scale = cfg.get("scale", f"{default_ow}:{default_oh}")
        safe_key = key.replace(' ', '_')
        filters.append(f"[{idx}:v]scale={scale}[img_{safe_key}]")

    # Scale cat images (small, corner overlay — 200px wide)
    for ci, cat_idx in enumerate(cat_input_indices):
        if cat_idx is not None:
            filters.append(f"[{cat_idx}:v]scale=200:-1[cat_{ci}]")

    # Scale reference images (~300px wide, centered opposite speaker)
    for ri, ref_idx in enumerate(ref_input_indices):
        filters.append(f"[{ref_idx}:v]scale=300:-1[ref_{ri}]")

    # Overlay speakers
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

    # Overlay cat images (top-right corner, brief appearances)
    for ci, (cat, cat_idx) in enumerate(zip(cat_overlays, cat_input_indices)):
        if cat_idx is None:
            continue
        # Position: top-right corner with some margin
        x_expr = f"W-overlay_w-{margin}"
        y_expr = str(margin)
        enable_expr = f"between(t,{cat['start']:.3f},{cat['end']:.3f})"
        out_label = f"v{overlay_counter}"
        filters.append(
            f"[{prev}][cat_{ci}]overlay={x_expr}:{y_expr}:"
            f"enable='{enable_expr}'[{out_label}]"
        )
        prev = out_label
        overlay_counter += 1

    # Overlay reference images (opposite side of speaker, vertically centered at ~25%)
    for ri, (ref, ref_idx) in enumerate(zip(ref_overlays, ref_input_indices)):
        x_expr = ref.get("x_expr", f"(W/2)-(overlay_w/2)")
        y_expr = f"(H*25/100)-(overlay_h/2)"
        enable_expr = f"between(t,{ref['start']:.3f},{ref['end']:.3f})"
        out_label = f"v{overlay_counter}"
        filters.append(
            f"[{prev}][ref_{ri}]overlay={x_expr}:{y_expr}:"
            f"enable='{enable_expr}'[{out_label}]"
        )
        prev = out_label
        overlay_counter += 1

    # ASS karaoke subtitles
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
        "-t", f"{total_duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Clean up temp files
    for tmp in (filter_script, ass_file):
        if os.path.exists(tmp):
            os.remove(tmp)

    if result.returncode != 0:
        raise RuntimeError(f"Compositing failed: {result.stderr}")


def _mix_sound_effects(ffmpeg, input_video, sfx_entries, duration, output_path):
    """Mix sound effects into the video at specific timestamps using FFmpeg."""
    # Strategy: create individual delayed+volume-adjusted SFX streams,
    # then amix them all with the original audio.

    inputs = ["-i", input_video]
    for sfx in sfx_entries:
        inputs.extend(["-i", sfx["path"].replace("\\", "/")])

    # Build filter: delay each SFX to its timestamp, adjust volume
    filter_parts = []
    mix_inputs = ["[0:a]"]

    for i, sfx in enumerate(sfx_entries):
        stream_idx = i + 1
        delay_ms = int(sfx["timestamp"] * 1000)
        vol = sfx["volume"]
        label = f"sfx{i}"
        filter_parts.append(
            f"[{stream_idx}:a]volume={vol},adelay={delay_ms}|{delay_ms}[{label}]"
        )
        mix_inputs.append(f"[{label}]")

    # Mix all together
    n_inputs = len(mix_inputs)
    mix_str = "".join(mix_inputs)
    filter_parts.append(
        f"{mix_str}amix=inputs={n_inputs}:duration=first:dropout_transition=2[aout]"
    )

    filter_complex = ";".join(filter_parts)

    # Write filter script to avoid shell quoting issues
    filter_script = output_path + ".sfx_filter.txt"
    with open(filter_script, "w", encoding="utf-8") as f:
        f.write(filter_complex)

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex_script", filter_script,
        "-map", "0:v",
        "-map", "[aout]",
        "-t", f"{duration:.3f}",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    print(f"  Mixing {len(sfx_entries)} sound effects...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(filter_script):
        os.remove(filter_script)

    if result.returncode != 0:
        print(f"  WARNING: SFX mixing failed, copying without SFX")
        print(f"  Error: {result.stderr[:200]}")
        # Fallback: just copy without SFX
        cmd = [ffmpeg, "-y", "-i", input_video, "-c", "copy", output_path]
        subprocess.run(cmd, capture_output=True, text=True)
    else:
        print(f"  -> Sound effects mixed successfully")


def _distribute(video_path):
    """Call Media_Distribution/post.py to distribute the video."""
    dist_dir = os.path.join(os.path.dirname(__file__), "..", "Media_Distribution")
    post_script = os.path.join(dist_dir, "post.py")

    if not os.path.exists(post_script):
        print(f"  ERROR: Media_Distribution/post.py not found at {post_script}")
        print(f"  Skipping distribution. Manually run:")
        print(f'    cd Media_Distribution && python post.py "{video_path}"')
        return

    yt_caption = CAPTIONS["youtube"]
    title = yt_caption["title"]
    description = yt_caption["description"]

    # Use the thumbnail from assets if available
    thumbnail = os.path.join(
        os.path.dirname(__file__), "assets", "thumbnail", "thumbnail.png"
    )
    thumb_arg = ["--thumbnail", thumbnail] if os.path.exists(thumbnail) else []

    cmd = [
        sys.executable, post_script,
        video_path,
        "--title", title,
        "--description", description,
        "--speakers", "Samay Raina,Tanmay Bhatt",
        *thumb_arg,
    ]

    print(f"  Running: post.py -> all platforms")
    print(f"  Title: {title[:60]}...")
    print()

    result = subprocess.run(
        cmd,
        cwd=dist_dir,
        text=True,
        timeout=1800,  # 30 min timeout for large uploads
    )

    if result.returncode != 0:
        print(f"  WARNING: Distribution exited with code {result.returncode}")
    else:
        print(f"  Distribution completed successfully!")


if __name__ == "__main__":
    main()
