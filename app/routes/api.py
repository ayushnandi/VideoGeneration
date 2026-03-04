from flask import Blueprint, jsonify

from app.services.job_manager import job_manager

api_bp = Blueprint("api", __name__)


@api_bp.route("/status/<job_id>")
def job_status(job_id):
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)
