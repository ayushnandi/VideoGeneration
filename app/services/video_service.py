import os
import shutil
import subprocess
import threading

from app.services.job_manager import job_manager
from app.services.tts_service import generate_tts


class VideoService:
    def __init__(self, app_config):
        self.config = app_config
        self.ffmpeg = app_config.get("FFMPEG_BIN", "ffmpeg")
        self.ffprobe = app_config.get("FFPROBE_BIN", "ffprobe")

    def run(self, job_id, dialogue):
        """Execute the full pipeline in a background thread."""
        t = threading.Thread(target=self._pipeline, args=(job_id, dialogue), daemon=True)
        t.start()

    def _pipeline(self, job_id, dialogue):
        job_dir = os.path.join(self.config["TEMP_DIR"], job_id)
        os.makedirs(job_dir, exist_ok=True)

        try:
            # Phase 1: TTS
            job_manager.update_job(job_id, status="tts", progress=5, message="Generating audio…")
            segments = self._generate_all_tts(job_id, job_dir, dialogue)

            # Phase 2: Timestamps
            timestamps = self._calculate_timestamps(segments)

            # Phase 3: Concat audio
            job_manager.update_job(
                job_id, status="compositing", progress=60, message="Merging audio…"
            )
            concat_audio = os.path.join(job_dir, "concat.wav")
            self._concat_audio(job_dir, segments, concat_audio)

            total_duration = timestamps[-1]["end"] if timestamps else 0

            # Phase 4: Prepare background (crop to 9:16)
            job_manager.update_job(job_id, progress=70, message="Preparing background…")
            bg_video = os.path.join(job_dir, "bg_loop.mp4")
            self._prepare_background(total_duration, bg_video)

            # Phase 5: Composite with speaker images
            job_manager.update_job(job_id, progress=80, message="Compositing video…")
            output_path = os.path.join(self.config["OUTPUT_DIR"], f"{job_id}.mp4")
            self._composite(bg_video, concat_audio, timestamps, dialogue, output_path)

            # Phase 6: Done
            job_manager.set_done(job_id, output_path)

        except Exception as e:
            job_manager.set_error(job_id, str(e))
        finally:
            # Phase 7: Cleanup temp
            if os.path.exists(job_dir):
                shutil.rmtree(job_dir, ignore_errors=True)

    def _generate_all_tts(self, job_id, job_dir, dialogue):
        speakers = self.config["SPEAKERS"]
        api_key = self.config["ELEVENLABS_API_KEY"]
        model = self.config["ELEVENLABS_MODEL"]
        ffprobe = self.ffprobe
        segments = []

        for i, line in enumerate(dialogue):
            speaker = line["speaker"].lower()
            speaker_cfg = speakers.get(speaker, speakers["default"])
            voice_id = speaker_cfg["voice_id"]

            audio_path = os.path.join(job_dir, f"line_{i:04d}.mp3")
            duration, word_timings = generate_tts(
                line["text"], voice_id, audio_path, api_key, model, ffprobe_bin=ffprobe
            )
            segments.append({"index": i, "path": audio_path, "duration": duration, "word_timings": word_timings})

            progress = int(10 + (i + 1) / len(dialogue) * 50)
            job_manager.update_job(
                job_id,
                progress=progress,
                message=f"TTS {i + 1}/{len(dialogue)}",
            )

        return segments

    def _calculate_timestamps(self, segments):
        timestamps = []
        current = 0.0
        for seg in segments:
            # Offset word timings to absolute time in the full audio
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
        return timestamps

    def _concat_audio(self, job_dir, segments, output_path):
        list_file = os.path.join(job_dir, "concat_list.txt")
        with open(list_file, "w") as f:
            for seg in segments:
                safe_path = seg["path"].replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-ar", "44100", "-ac", "2",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Audio concat failed: {result.stderr}")

    def _prepare_background(self, duration, output_path):
        """Crop landscape video to 9:16 portrait and trim to duration."""
        bg_src = self.config["BACKGROUND_VIDEO"]
        width = self.config["VIDEO_WIDTH"]
        height = self.config["VIDEO_HEIGHT"]

        # Crop center of landscape to 9:16 ratio, then scale to target resolution
        cmd = [
            self.ffmpeg, "-y",
            "-stream_loop", "-1",
            "-i", bg_src,
            "-t", str(duration),
            "-vf",
            f"crop=in_h*9/16:in_h,scale={width}:{height}",
            "-an",
            "-c:v", "libx264", "-preset", "fast",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Background prep failed: {result.stderr}")

    # ── subtitle helpers (ASS karaoke) ─────────────────────────────

    @staticmethod
    def _sanitize_ass_text(text):
        """Remove characters that break ASS subtitle parsing."""
        text = text.replace("\\", "")
        text = text.replace("{", "(")
        text = text.replace("}", ")")
        text = text.replace("\u2026", "...")
        text = text.replace("\u2019", "'")
        text = text.replace("\n", " ")
        return text

    @staticmethod
    def _ass_timestamp(seconds):
        """Convert seconds to ASS timestamp format H:MM:SS.CC"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def _generate_ass_file(self, timestamps, dialogue, ass_path):
        """Generate an ASS subtitle file with karaoke-style word highlighting.

        Uses real word-level timestamps from ElevenLabs when available,
        so each word lights up exactly when the speaker says it.
        Falls back to equal distribution when word timings are missing.
        """
        font_name = self.config.get("FONT_NAME", "Poppins ExtraBold")
        font_size = self.config.get("SUBTITLE_FONT_SIZE", 58)
        highlight_extra = self.config.get("SUBTITLE_HIGHLIGHT_EXTRA_SIZE", 4)
        highlight_size = font_size + highlight_extra
        vid_w = self.config["VIDEO_WIDTH"]
        vid_h = self.config["VIDEO_HEIGHT"]
        words_per = self.config.get("SUBTITLE_WORDS_PER_CHUNK", 4)

        # Subtitle vertical position — above middle (~38% from top)
        sub_margin_v = int(vid_h * 0.38)

        # ASS header — Alignment 8 = top-center, MarginV pushes down
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {vid_w}",
            f"PlayResY: {vid_h}",
            "WrapStyle: 0",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{font_name},{font_size},"
            "&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,1,3,0,8,10,10,{sub_margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, "
            "MarginL, MarginR, MarginV, Effect, Text",
        ]

        for ts, line in zip(timestamps, dialogue):
            all_words = line["text"].split()
            if not all_words:
                continue

            word_timings = ts.get("word_timings", [])

            # Build per-word timing: use real timings if available
            if word_timings and len(word_timings) == len(all_words):
                per_word = word_timings
            elif word_timings and len(word_timings) > 0:
                per_word = self._redistribute_timings(
                    all_words, word_timings, ts["start"], ts["end"]
                )
            else:
                line_dur = ts["end"] - ts["start"]
                word_dur = line_dur / len(all_words)
                per_word = []
                for wi, w in enumerate(all_words):
                    per_word.append({
                        "word": w,
                        "start": ts["start"] + wi * word_dur,
                        "end": ts["start"] + (wi + 1) * word_dur,
                    })

            # Split words into display chunks
            n_chunks = max(1, -(-len(all_words) // words_per))
            for ci in range(n_chunks):
                si = ci * words_per
                ei = min(si + words_per, len(all_words))
                chunk_words = all_words[si:ei]
                chunk_timings = per_word[si:ei]

                # Chunk time span: first word start → last word end
                chunk_start = chunk_timings[0]["start"]
                chunk_end = chunk_timings[-1]["end"]

                # Continuous highlighting: each word's event spans from
                # its start to the next word's start (no gaps/disappearing).
                # Last word spans to chunk_end.
                for wi in range(len(chunk_words)):
                    ev_start = chunk_timings[wi]["start"]
                    if wi + 1 < len(chunk_words):
                        ev_end = chunk_timings[wi + 1]["start"]
                    else:
                        ev_end = chunk_end

                    parts = []
                    for wj, w in enumerate(chunk_words):
                        clean = self._sanitize_ass_text(w)
                        if wj == wi:
                            parts.append(
                                f"{{\\c&H00FFFF&\\fs{highlight_size}}}"
                                f"{clean}"
                                f"{{\\r}}"
                            )
                        else:
                            parts.append(clean)

                    text = " ".join(parts)
                    start_str = self._ass_timestamp(ev_start)
                    end_str = self._ass_timestamp(ev_end)
                    lines.append(
                        f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}"
                    )

        with open(ass_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines) + "\n")

    @staticmethod
    def _redistribute_timings(text_words, api_timings, line_start, line_end):
        """When word count from text.split() differs from API alignment,
        map API timings onto text words proportionally."""
        n = len(text_words)
        total_dur = line_end - line_start
        if total_dur <= 0:
            total_dur = 0.001

        # Use total character count to assign proportional durations
        total_chars = sum(len(w) for w in text_words)
        if total_chars == 0:
            total_chars = n

        # Use API's overall time span
        api_start = api_timings[0]["start"] if api_timings else line_start
        api_end = api_timings[-1]["end"] if api_timings else line_end

        result = []
        cursor = api_start
        for w in text_words:
            proportion = len(w) / total_chars
            w_dur = (api_end - api_start) * proportion
            result.append({"word": w, "start": cursor, "end": cursor + w_dur})
            cursor += w_dur

        return result

    # ── main composite ────────────────────────────────────────────

    def _composite(self, bg_video, audio, timestamps, dialogue, output_path):
        speakers = self.config["SPEAKERS"]
        speakers_dir = self.config["SPEAKERS_DIR"]
        vid_w = self.config["VIDEO_WIDTH"]
        vid_h = self.config["VIDEO_HEIGHT"]
        default_ow = self.config["OVERLAY_WIDTH"]
        default_oh = self.config["OVERLAY_HEIGHT"]

        margin = 30
        bottom_margin = 120

        # ── collect unique speakers and their images ──────────────
        speaker_images = {}  # speaker_key → abs image path
        for line in dialogue:
            key = line["speaker"].lower()
            if key not in speaker_images:
                cfg = speakers.get(key, speakers["default"])
                speaker_images[key] = os.path.join(speakers_dir, cfg["image"])

        # ── build FFmpeg inputs ──────────────────────────────────
        # 0 = bg video, 1 = audio, 2+ = speaker images
        inputs = ["-i", bg_video, "-i", audio]
        speaker_idx = {}  # speaker_key → ffmpeg input index
        next_idx = 2
        for key, img_path in speaker_images.items():
            inputs.extend(["-loop", "1", "-i", img_path])
            speaker_idx[key] = next_idx
            next_idx += 1

        # ── build filter_complex ─────────────────────────────────
        filters = []
        total_duration = timestamps[-1]["end"] if timestamps else 0

        # Scale each speaker image (per-speaker scale preserving aspect ratio)
        for key, idx in speaker_idx.items():
            cfg = speakers.get(key, speakers["default"])
            scale = cfg.get("scale", f"{default_ow}:{default_oh}")
            safe_key = key.replace(' ', '_')
            filters.append(f"[{idx}:v]scale={scale}[img_{safe_key}]")

        # Overlay each speaker only during their lines
        # Use overlay_w/overlay_h to compute position dynamically
        prev = "0:v"
        overlay_counter = 0
        for key, idx in speaker_idx.items():
            cfg = speakers.get(key, speakers["default"])
            position = cfg.get("position", "right")
            safe_key = key.replace(' ', '_')

            # x position based on layout
            if position == "center-left":
                # center image at ~30% of screen width
                x_expr = f"(W*30/100)-(overlay_w/2)"
            elif position == "center-right":
                # center image at ~70% of screen width
                x_expr = f"(W*70/100)-(overlay_w/2)"
            elif position == "left":
                x_expr = str(margin)
            else:
                x_expr = f"W-overlay_w-{margin}"

            # y: below-middle (center image at ~58% of screen height)
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

        # ── ASS karaoke subtitles ──────────────────────────────────
        ass_file = output_path + ".ass"
        fonts_dir = os.path.join(self.config["ASSETS_DIR"], "fonts")
        self._generate_ass_file(timestamps, dialogue, ass_file)

        # Escape paths for FFmpeg filter syntax (\: for drive colon)
        ass_path_ff = ass_file.replace("\\", "/").replace(":", "\\:")
        fonts_dir_ff = fonts_dir.replace("\\", "/").replace(":", "\\:")

        filters.append(
            f"[{prev}]ass='{ass_path_ff}':fontsdir='{fonts_dir_ff}'[final]"
        )
        final_label = "final"

        filter_complex = ";".join(filters)

        # Write filter to a script file to avoid shell quoting issues
        filter_script = output_path + ".filtergraph.txt"
        with open(filter_script, "w", encoding="utf-8") as f:
            f.write(filter_complex)

        cmd = [
            self.ffmpeg, "-y",
            *inputs,
            "-filter_complex_script", filter_script,
            "-map", f"[{final_label}]",
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

    # Public API for backward compatibility
    def compose_video(self, bg_video, audio, timestamps, dialogue, image_map, output_path):
        # image_map is unused by internal compositor; kept for compatibility with existing scripts
        self._composite(bg_video, audio, timestamps, dialogue, output_path)
