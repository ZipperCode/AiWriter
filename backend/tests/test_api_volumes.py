async def _create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers
    )
    return resp.json()["id"]


async def test_create_volume(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.post(
        f"/api/projects/{pid}/volumes",
        json={"title": "第一卷", "objective": "主角觉醒"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "第一卷"


async def test_list_volumes(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    await client.post(
        f"/api/projects/{pid}/volumes",
        json={"title": "V1", "objective": "O1"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/projects/{pid}/volumes",
        json={"title": "V2", "objective": "O2"},
        headers=auth_headers,
    )
    resp = await client.get(f"/api/projects/{pid}/volumes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_update_volume(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    cr = await client.post(
        f"/api/projects/{pid}/volumes",
        json={"title": "Old", "objective": "X"},
        headers=auth_headers,
    )
    vid = cr.json()["id"]
    resp = await client.put(
        f"/api/volumes/{vid}", json={"title": "New"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"


async def test_delete_volume(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    cr = await client.post(
        f"/api/projects/{pid}/volumes",
        json={"title": "Del", "objective": "X"},
        headers=auth_headers,
    )
    vid = cr.json()["id"]
    resp = await client.delete(f"/api/volumes/{vid}", headers=auth_headers)
    assert resp.status_code == 204
