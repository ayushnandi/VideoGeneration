import json
import os

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from app.services.job_manager import job_manager
from app.services.video_service import VideoService
from app.utils.validators import validate_dialogue

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("dialogue_file")
    if not file or not file.filename:
        return render_template("index.html", error="No file selected.")

    if not file.filename.endswith(".json"):
        return render_template("index.html", error="File must be a .json file.")

    try:
        data = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return render_template("index.html", error="Invalid JSON file.")

    dialogue, error = validate_dialogue(data)
    if error:
        return render_template("index.html", error=error)

    # Create job and start processing
    job_id = job_manager.create_job()
    service = VideoService(current_app.config)
    service.run(job_id, dialogue)

    return redirect(url_for("main.status", job_id=job_id))


@main_bp.route("/status/<job_id>")
def status(job_id):
    job = job_manager.get_job(job_id)
    if not job:
        return render_template("index.html", error="Job not found."), 404
    return render_template("status.html", job_id=job_id, job=job)


@main_bp.route("/download/<job_id>")
def download(job_id):
    job = job_manager.get_job(job_id)
    if not job or job["status"] != "done":
        return redirect(url_for("main.status", job_id=job_id))

    output_path = job["output_path"]
    if not output_path or not os.path.exists(output_path):
        return render_template("index.html", error="Output file not found."), 404

    return send_file(output_path, as_attachment=True, download_name=f"{job_id}.mp4")
