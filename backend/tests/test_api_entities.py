async def _create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers
    )
    return resp.json()["id"]


async def test_create_entity(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.post(
        f"/api/projects/{pid}/entities",
        json={
            "name": "叶辰",
            "entity_type": "character",
            "aliases": ["叶少", "辰哥"],
            "attributes": {"personality": "冷傲"},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "叶辰"
    assert data["aliases"] == ["叶少", "辰哥"]
    assert data["confidence"] == 1.0


async def test_list_entities_with_type_filter(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    await client.post(
        f"/api/projects/{pid}/entities",
        json={"name": "叶辰", "entity_type": "character"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/projects/{pid}/entities",
        json={"name": "青云宗", "entity_type": "faction"},
        headers=auth_headers,
    )

    # All entities
    resp = await client.get(f"/api/projects/{pid}/entities", headers=auth_headers)
    assert resp.json()["total"] == 2

    # Filter by type
    resp = await client.get(
        f"/api/projects/{pid}/entities?entity_type=character", headers=auth_headers
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "叶辰"


async def test_create_relationship(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    e1 = await client.post(
        f"/api/projects/{pid}/entities",
        json={"name": "叶辰", "entity_type": "character"},
        headers=auth_headers,
    )
    e2 = await client.post(
        f"/api/projects/{pid}/entities",
        json={"name": "苏灵儿", "entity_type": "character"},
        headers=auth_headers,
    )

    resp = await client.post(
        f"/api/projects/{pid}/relationships",
        json={
            "source_entity_id": e1.json()["id"],
            "target_entity_id": e2.json()["id"],
            "relation_type": "lover",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["relation_type"] == "lover"


async def test_graph_query_not_implemented(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/projects/{pid}/graph", headers=auth_headers)
    assert resp.status_code == 501
