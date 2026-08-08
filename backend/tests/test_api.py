"""test_api.py: workflows CRUD、nodes 列表、estimate、run 链路 (SPEC §11)."""
import asyncio


def _prompt_wf(text="hello"):
    return {"version": 1, "name": "t",
            "nodes": [{"id": "n1", "type": "prompt", "position": {"x": 0, "y": 0},
                       "config": {"text": text}}],
            "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


def _paid_wf():
    return {"version": 1, "name": "paid",
            "nodes": [
                {"id": "n1", "type": "prompt", "position": {"x": 0, "y": 0}, "config": {"text": "cat"}},
                {"id": "n2", "type": "video_generation", "position": {"x": 300, "y": 0},
                 "config": {"duration": 6}},
            ],
            "edges": [{"id": "e1", "source": "n1", "source_handle": "prompt",
                       "target": "n2", "target_handle": "prompt"}],
            "viewport": {"x": 0, "y": 0, "zoom": 1}}


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_nodes_list(client):
    resp = await client.get("/api/nodes")
    assert resp.status_code == 200
    schemas = resp.json()
    types = {s["type"] for s in schemas}
    # 内置 19 个节点必须全部存在（测试模块可能额外注册 fake 节点）
    builtin = {"prompt", "text", "combine_prompt", "variables", "character_context",
               "scene_context", "style_context", "llm", "prompt_optimizer", "storyboard",
               "json_parser", "image_input", "video_generation",
               "last_frame", "frame_extract", "video_preview", "video_merge", "save_file"}
    assert builtin <= types
    assert {"prompt", "prompt_optimizer", "video_generation", "video_merge",
            "storyboard", "json_parser", "save_file"} <= types
    vg = next(s for s in schemas if s["type"] == "video_generation")
    assert vg["is_paid"] is True
    assert any(p["key"] == "prompt" and p["required"] for p in vg["inputs"])
    # config_schema 里的 credential 字段带 provider_kind
    cred_field = next(c for c in vg["config_schema"] if c["key"] == "credential_id")
    assert cred_field["type"] == "credential"
    assert cred_field["provider_kind"] == "video"


async def test_workflows_crud(client):
    # create
    resp = await client.post("/api/workflows", json={"name": "wf1", "data": _prompt_wf()})
    assert resp.status_code == 201
    wf = resp.json()
    wf_id = wf["id"]
    assert wf["data"]["nodes"][0]["type"] == "prompt"

    # list
    lst = await client.get("/api/workflows")
    assert any(w["id"] == wf_id for w in lst.json())
    assert "data" not in lst.json()[0]  # 列表不含 data

    # get
    got = await client.get(f"/api/workflows/{wf_id}")
    assert got.json()["name"] == "wf1"

    # update
    upd = await client.put(f"/api/workflows/{wf_id}", json={"name": "wf1-renamed"})
    assert upd.json()["name"] == "wf1-renamed"

    # duplicate
    dup = await client.post(f"/api/workflows/{wf_id}/duplicate")
    assert dup.status_code == 201
    assert dup.json()["id"] != wf_id
    assert "copy" in dup.json()["name"]

    # delete
    assert (await client.delete(f"/api/workflows/{wf_id}")).status_code == 204
    assert (await client.get(f"/api/workflows/{wf_id}")).status_code == 404


async def test_workflow_rejects_secret_in_data(client):
    bad = _prompt_wf()
    bad["nodes"][0]["config"]["api_key"] = "sk-leak"
    resp = await client.post("/api/workflows", json={"name": "bad", "data": bad})
    assert resp.status_code == 400


async def test_estimate(client):
    resp = await client.post("/api/workflows", json={"name": "p", "data": _paid_wf()})
    wf_id = resp.json()["id"]
    est = await client.post(f"/api/workflows/{wf_id}/estimate")
    assert est.status_code == 200
    body = est.json()
    assert body["paid_node_count"] == 1
    assert body["estimated_api_calls"] >= 1
    assert body["estimated_video_seconds"] == 6.0
    assert body["estimated_cost"] is None  # 未设置单价
    assert any("Cost unavailable" in n for n in body["notes"])
    assert body["currency"] == "USD"


async def test_estimate_with_pricing_setting(client):
    await client.put("/api/settings", json={"pricing": {"minimax": {"per_second": 0.5}}})
    resp = await client.post("/api/workflows", json={"name": "p", "data": _paid_wf()})
    wf_id = resp.json()["id"]
    body = (await client.post(f"/api/workflows/{wf_id}/estimate")).json()
    assert body["estimated_cost"] == 3.0


async def test_templates(client):
    resp = await client.get("/api/templates")
    assert resp.status_code == 200
    templates = {t["id"]: t for t in resp.json()}
    assert {"text_to_video", "image_to_video", "last_frame_continue",
            "three_shot_movie", "story_to_storyboard"} <= set(templates)
    t2v = templates["text_to_video"]["data"]
    assert [n["type"] for n in t2v["nodes"]] == ["prompt", "prompt_optimizer",
                                                "video_generation", "video_preview"]
    assert len(t2v["edges"]) == 3
    # 每个视频类模板末端都必须有视频预览节点
    for tid in ("text_to_video", "image_to_video", "last_frame_continue", "three_shot_movie"):
        types = [n["type"] for n in templates[tid]["data"]["nodes"]]
        assert "video_preview" in types, tid


async def test_run_local_workflow_end_to_end(client):
    resp = await client.post("/api/workflows", json={"name": "local", "data": _prompt_wf("hi there")})
    wf_id = resp.json()["id"]
    run_resp = await client.post(f"/api/workflows/{wf_id}/run", json={"confirm_paid": False})
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    for _ in range(50):
        await asyncio.sleep(0.1)
        run = (await client.get(f"/api/runs/{run_id}")).json()
        if run["status"] in ("success", "failed", "cancelled"):
            break
    assert run["status"] == "success"
    assert run["node_runs"][0]["status"] == "SUCCESS"
    assert run["node_runs"][0]["outputs"]["prompt"] == "hi there"


async def test_paid_run_requires_confirmation(client):
    resp = await client.post("/api/workflows", json={"name": "p", "data": _paid_wf()})
    wf_id = resp.json()["id"]
    run_resp = await client.post(f"/api/workflows/{wf_id}/run", json={"confirm_paid": False})
    assert run_resp.status_code == 202
    body = run_resp.json()
    assert body["status"] == "waiting_confirmation"
    assert body["estimate"]["paid_node_count"] == 1

    run = (await client.get(f"/api/runs/{body['run_id']}")).json()
    assert run["status"] == "waiting_confirmation"

    # confirm 后真正执行（无 credential，video 节点会失败，但流程必须走通不崩溃）
    confirm = await client.post(f"/api/runs/{body['run_id']}/confirm")
    assert confirm.status_code == 200
    for _ in range(50):
        await asyncio.sleep(0.1)
        run = (await client.get(f"/api/runs/{body['run_id']}")).json()
        if run["status"] in ("success", "failed", "cancelled"):
            break
    assert run["status"] == "failed"  # video_generation 无 credential → FAILED
    statuses = {nr["node_id"]: nr["status"] for nr in run["node_runs"]}
    assert statuses["n1"] == "SUCCESS"
    assert statuses["n2"] == "FAILED"


async def test_file_traversal_protection(client):
    assert (await client.get("/api/files/../../etc/passwd")).status_code in (403, 404)
    assert (await client.get("/api/files/outputs/../../../etc/passwd")).status_code in (403, 404)


async def test_workflow_backup_and_trash(client, tmp_path, monkeypatch):
    """保存留最新备份、删除进回收站（防数据丢失安全网）。"""
    from app.services import backup as backup_service

    monkeypatch.setattr(backup_service, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_service, "TRASH_DIR", tmp_path / "trash")
    # api 模块在 import 时已绑定函数引用，patch 其命名空间
    import app.api.workflows as wf_api
    monkeypatch.setattr(wf_api, "backup_workflow", backup_service.backup_workflow)
    monkeypatch.setattr(wf_api, "trash_workflow", backup_service.trash_workflow)

    resp = await client.post("/api/workflows", json={"name": "备份测试", "data": _prompt_wf("backup")})
    assert resp.status_code == 201
    wf_id = resp.json()["id"]
    backup_file = tmp_path / "backups" / f"{wf_id}.json"
    assert backup_file.exists()

    data = resp.json()["data"]
    data["name"] = "备份测试-改名"
    resp = await client.put(f"/api/workflows/{wf_id}", json={"name": "备份测试-改名", "data": data})
    assert resp.status_code == 200
    import json as _json
    assert _json.loads(backup_file.read_text(encoding="utf-8"))["name"] == "备份测试-改名"

    resp = await client.delete(f"/api/workflows/{wf_id}")
    assert resp.status_code == 204
    trashed = list((tmp_path / "trash").glob(f"*_{wf_id}.json"))
    assert len(trashed) == 1
    assert _json.loads(trashed[0].read_text(encoding="utf-8"))["data"]["nodes"]
