async def test_create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects",
        json={"title": "仙侠奇缘", "genre": "xianxia"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "仙侠奇缘"
    assert data["genre"] == "xianxia"
    assert "id" in data


async def test_list_projects(client, auth_headers):
    await client.post(
        "/api/projects", json={"title": "P1", "genre": "xuanhuan"}, headers=auth_headers
    )
    await client.post(
        "/api/projects", json={"title": "P2", "genre": "urban"}, headers=auth_headers
    )

    resp = await client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


async def test_get_project(client, auth_headers):
    create_resp = await client.post(
        "/api/projects",
        json={"title": "Get Test", "genre": "horror"},
        headers=auth_headers,
    )
    pid = create_resp.json()["id"]

    resp = await client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Test"


async def test_update_project(client, auth_headers):
    create_resp = await client.post(
        "/api/projects",
        json={"title": "Old Title", "genre": "scifi"},
        headers=auth_headers,
    )
    pid = create_resp.json()["id"]

    resp = await client.put(
        f"/api/projects/{pid}",
        json={"title": "New Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


async def test_delete_project(client, auth_headers):
    create_resp = await client.post(
        "/api/projects",
        json={"title": "To Delete", "genre": "romance"},
        headers=auth_headers,
    )
    pid = create_resp.json()["id"]

    resp = await client.delete(f"/api/projects/{pid}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert resp.status_code == 404
