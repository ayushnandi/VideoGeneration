from flask import Blueprint, current_app, jsonify, request

from app.services.job_manager import job_manager
from app.services.video_service import VideoService
from app.utils.validators import validate_dialogue

api_bp = Blueprint("api", __name__)


@api_bp.route("/status/<job_id>")
def job_status(job_id):
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@api_bp.route("/generate", methods=["POST"])
def generate():
    """Programmatic API: accept dialogue JSON and return job_id.

    POST /api/generate
    Content-Type: application/json
    Body: {"dialogue": [{"speaker": "samay", "text": "..."}, ...]}
    Response: {"job_id": "...", "status": "processing"}
    """
    data = request.get_json()
    if not data or "dialogue" not in data:
        return jsonify({"error": "Missing 'dialogue' field"}), 400

    dialogue, error = validate_dialogue(data["dialogue"])
    if error:
        return jsonify({"error": error}), 400

    job_id = job_manager.create_job()
    service = VideoService(current_app.config)
    service.run(job_id, dialogue)

    return jsonify({"job_id": job_id, "status": "processing"})
