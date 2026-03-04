import threading
import uuid


class JobManager:
    """Thread-safe in-memory job state tracker."""

    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def create_job(self):
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "status": "pending",
                "progress": 0,
                "message": "Job created",
                "error": None,
                "output_path": None,
            }
        return job_id

    def get_job(self, job_id):
        with self._lock:
            return self._jobs.get(job_id, {}).copy()

    def update_job(self, job_id, **kwargs):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def set_error(self, job_id, error_msg):
        self.update_job(job_id, status="error", error=error_msg, message="Failed")

    def set_done(self, job_id, output_path):
        self.update_job(
            job_id,
            status="done",
            progress=100,
            message="Complete",
            output_path=output_path,
        )


# Singleton instance
job_manager = JobManager()
