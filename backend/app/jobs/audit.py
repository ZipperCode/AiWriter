"""Celery tasks for audit pipeline (audit queue)."""

from app.jobs.celery_app import celery_app


@celery_app.task(queue="audit", bind=True, max_retries=2)
def run_chapter_audit(
    self, chapter_id: str, draft_id: str, job_id: str, mode: str = "full"
):
    return {"status": "completed", "job_id": job_id}
