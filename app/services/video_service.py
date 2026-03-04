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
            duration = generate_tts(
                line["text"], voice_id, audio_path, api_key, model, ffprobe_bin=ffprobe
            )

            segments.append({"index": i, "path": audio_path, "duration": duration})

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
            timestamps.append({"start": current, "end": current + seg["duration"]})
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

    # ── subtitle helpers ────────────────────────────────────────────

    @staticmethod
    def _escape_drawtext(text):
        """Escape special characters for FFmpeg drawtext filter."""
        # Order matters: backslash first, then the rest
        for ch in ["\\", "'", ":", "%"]:
            text = text.replace(ch, f"\\{ch}")
        return text

    def _build_subtitle_chunks(self, timestamps, dialogue):
        """Split each dialogue line into N-word chunks with timed windows."""
        words_per = self.config.get("SUBTITLE_WORDS_PER_CHUNK", 4)
        chunks = []
        for ts, line in zip(timestamps, dialogue):
            words = line["text"].split()
            n_chunks = max(1, -(-len(words) // words_per))  # ceil division
            line_dur = ts["end"] - ts["start"]
            chunk_dur = line_dur / n_chunks
            for ci in range(n_chunks):
                start_word = ci * words_per
                end_word = min(start_word + words_per, len(words))
                chunk_text = " ".join(words[start_word:end_word])
                chunk_start = ts["start"] + ci * chunk_dur
                chunk_end = chunk_start + chunk_dur
                chunks.append({
                    "text": chunk_text,
                    "start": chunk_start,
                    "end": chunk_end,
                })
        return chunks

    # ── main composite ────────────────────────────────────────────

    def _composite(self, bg_video, audio, timestamps, dialogue, output_path):
        speakers = self.config["SPEAKERS"]
        speakers_dir = self.config["SPEAKERS_DIR"]
        ow = self.config["OVERLAY_WIDTH"]
        oh = self.config["OVERLAY_HEIGHT"]
        vid_w = self.config["VIDEO_WIDTH"]
        vid_h = self.config["VIDEO_HEIGHT"]

        margin = 30
        y_pos = vid_h - oh - 120
        pos_left_x = margin
        pos_right_x = vid_w - ow - margin

        # ── resolve font path (Inter-Bold → Arial fallback) ──────
        font_path = self.config.get("FONT_PATH", "")
        if not font_path or not os.path.exists(font_path):
            font_path = r"C:/Windows/Fonts/arial.ttf"
        # FFmpeg on Windows needs forward slashes & escaped colons
        font_path_ff = font_path.replace("\\", "/").replace(":", "\\:")
        font_size = self.config.get("SUBTITLE_FONT_SIZE", 48)

        # ── toji image (constant, right side, always visible) ────
        toji_cfg = speakers.get("toji", speakers["default"])
        toji_img = os.path.join(speakers_dir, toji_cfg["image"])

        # ── collect unique cat images & map lines → image key ────
        unique_cat_images = {}   # key (relative path) → absolute path
        line_cat_key = []        # per-line: which cat image key
        for line in dialogue:
            cat_rel = line.get("cat_image", "cat/innocent_cat.jpg")
            if cat_rel not in unique_cat_images:
                unique_cat_images[cat_rel] = os.path.join(speakers_dir, cat_rel)
            line_cat_key.append(cat_rel)

        # ── build FFmpeg inputs ──────────────────────────────────
        # 0 = bg video, 1 = audio, 2 = toji image, 3+ = unique cat images
        inputs = ["-i", bg_video, "-i", audio]
        inputs.extend(["-loop", "1", "-i", toji_img])
        toji_idx = 2

        cat_img_idx = {}  # cat_rel → ffmpeg input index
        next_idx = 3
        for cat_rel, abs_path in unique_cat_images.items():
            inputs.extend(["-loop", "1", "-i", abs_path])
            cat_img_idx[cat_rel] = next_idx
            next_idx += 1

        # ── build filter_complex ─────────────────────────────────
        filters = []

        # Scale toji once
        filters.append(f"[{toji_idx}:v]scale={ow}:{oh}[img_toji]")

        # Scale each unique cat image
        for cat_rel, idx in cat_img_idx.items():
            safe_label = f"img_cat_{idx}"
            filters.append(f"[{idx}:v]scale={ow}:{oh}[{safe_label}]")

        # ── toji overlay: always visible for full duration ───────
        total_duration = timestamps[-1]["end"] if timestamps else 0
        enable_all = f"between(t,0,{total_duration:.3f})"
        filters.append(
            f"[0:v][img_toji]overlay={pos_right_x}:{y_pos}:"
            f"enable='{enable_all}'[v_toji]"
        )

        # ── cat overlays: one per unique image, with combined enable ─
        # Group line time windows by cat image key
        cat_time_windows = {}
        for i, cat_rel in enumerate(line_cat_key):
            if cat_rel not in cat_time_windows:
                cat_time_windows[cat_rel] = []
            cat_time_windows[cat_rel].append(
                f"between(t,{timestamps[i]['start']:.3f},{timestamps[i]['end']:.3f})"
            )

        prev = "v_toji"
        overlay_counter = 0
        for cat_rel, windows in cat_time_windows.items():
            idx = cat_img_idx[cat_rel]
            safe_label = f"img_cat_{idx}"
            enable_expr = "+".join(windows)
            out_label = f"v{overlay_counter}"
            filters.append(
                f"[{prev}][{safe_label}]overlay={pos_left_x}:{y_pos}:"
                f"enable='{enable_expr}'[{out_label}]"
            )
            prev = out_label
            overlay_counter += 1

        # ── subtitle drawtext filters ────────────────────────────
        chunks = self._build_subtitle_chunks(timestamps, dialogue)
        subtitle_y = y_pos - 80  # just above speaker images

        drawtext_parts = []
        for chunk in chunks:
            escaped = self._escape_drawtext(chunk["text"])
            dt = (
                f"drawtext=text='{escaped}'"
                f":fontfile='{font_path_ff}'"
                f":fontsize={font_size}"
                f":fontcolor=yellow"
                f":borderw=2:bordercolor=black"
                f":x=(w-text_w)/2"
                f":y={subtitle_y}"
                f":enable='between(t,{chunk['start']:.3f},{chunk['end']:.3f})'"
            )
            drawtext_parts.append(dt)

        # Chain drawtext as comma-separated filters on the last overlay output
        if drawtext_parts:
            dt_chain = ",".join(drawtext_parts)
            filters.append(f"[{prev}]{dt_chain}[final]")
            final_label = "final"
        else:
            final_label = prev

        filter_complex = ";".join(filters)

        cmd = [
            self.ffmpeg, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{final_label}]",
            "-map", "1:a",
            "-t", f"{total_duration:.3f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Compositing failed: {result.stderr}")
