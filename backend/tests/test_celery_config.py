from app.jobs.celery_app import celery_app


def test_celery_app_exists():
    assert celery_app is not None
    assert celery_app.main == "aiwriter"


def test_celery_queues_configured():
    queues = celery_app.conf.task_queues
    queue_names = {q.name for q in queues}
    assert "default" in queue_names
    assert "writing" in queue_names
    assert "audit" in queue_names


def test_celery_default_queue():
    assert celery_app.conf.task_default_queue == "default"


def test_celery_serializer():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
