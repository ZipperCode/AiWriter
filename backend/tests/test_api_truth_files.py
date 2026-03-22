async def _create_project(client, auth_headers):
    resp = await client.post("/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers)
    return resp.json()["id"]


async def test_list_truth_files(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/projects/{pid}/truth-files", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 10


async def test_get_truth_file(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/projects/{pid}/truth-files/story_bible", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_type"] == "story_bible"
    assert data["version"] == 1


async def test_get_truth_file_not_found(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/projects/{pid}/truth-files/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_truth_file_history(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/projects/{pid}/truth-files/story_bible/history", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
