async def _create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers
    )
    return resp.json()["id"]


async def test_create_chapter(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "第一章 天降奇缘"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "第一章 天降奇缘"
    assert resp.json()["status"] == "planned"


async def test_list_chapters_with_volume_filter(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    # Create a volume
    vr = await client.post(
        f"/api/projects/{pid}/volumes",
        json={"title": "V1", "objective": "O1"},
        headers=auth_headers,
    )
    vid = vr.json()["id"]

    # Create chapters — one with volume, one without
    await client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "C1", "volume_id": vid},
        headers=auth_headers,
    )
    await client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "C2"},
        headers=auth_headers,
    )

    # All chapters
    resp = await client.get(f"/api/projects/{pid}/chapters", headers=auth_headers)
    assert resp.json()["total"] == 2

    # Filter by volume
    resp = await client.get(
        f"/api/projects/{pid}/chapters?volume_id={vid}", headers=auth_headers
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "C1"


async def test_update_chapter_status(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    cr = await client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "Ch1"},
        headers=auth_headers,
    )
    cid = cr.json()["id"]
    resp = await client.put(
        f"/api/chapters/{cid}", json={"status": "writing"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "writing"
