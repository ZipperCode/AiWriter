async def test_health_no_auth(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_protected_endpoint_no_token(client):
    resp = await client.get("/api/projects")
    assert resp.status_code in (401, 403)


async def test_protected_endpoint_wrong_token(client):
    resp = await client.get("/api/projects", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code in (401, 403)


async def test_protected_endpoint_valid_token(client, auth_headers):
    resp = await client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
