"""Celery tasks for writing pipeline (writing queue)."""

from app.jobs.celery_app import celery_app


@celery_app.task(queue="writing", bind=True, max_retries=2)
def run_chapter_pipeline(self, project_id: str, chapter_id: str, job_id: str):
    return {"status": "completed", "job_id": job_id}
