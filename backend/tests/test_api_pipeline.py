from uuid import uuid4


async def _create_project(client, auth_headers):
    resp = await client.post("/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers)
    return resp.json()["id"]


async def test_create_job_run(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.post(f"/api/projects/{pid}/pipeline/write-chapter", json={"chapter_id": str(uuid4())}, headers=auth_headers)
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["job_type"] == "pipeline_write"


async def test_get_job_status(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    create_resp = await client.post(f"/api/projects/{pid}/pipeline/write-chapter", json={"chapter_id": str(uuid4())}, headers=auth_headers)
    job_id = create_resp.json()["id"]
    resp = await client.get(f"/api/pipeline/jobs/{job_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


async def test_get_job_not_found(client, auth_headers):
    resp = await client.get(f"/api/pipeline/jobs/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
