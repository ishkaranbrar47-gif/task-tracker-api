import pytest

from app import create_app
from app.validation import ValidationError, validate_task


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.sqlite"))
    app.config["TESTING"] = True
    return app.test_client()


def make(client, **fields):
    body = {"title": "Write report", **fields}
    res = client.post("/tasks", json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


# --- health -----------------------------------------------------------------

def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


# --- create -----------------------------------------------------------------

def test_create_uses_defaults(client):
    task = make(client)
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["due_date"] is None


def test_create_sets_location_header(client):
    res = client.post("/tasks", json={"title": "Call supplier"})
    assert res.headers["Location"] == f"/tasks/{res.get_json()['id']}"


def test_create_trims_title(client):
    assert make(client, title="  Spaces  ")["title"] == "Spaces"


@pytest.mark.parametrize(
    "body, field",
    [
        ({}, "title"),
        ({"title": "   "}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"title": "ok", "status": "finished"}, "status"),
        ({"title": "ok", "priority": "urgent"}, "priority"),
        ({"title": "ok", "due_date": "12/01/2026"}, "due_date"),
        ({"title": "ok", "owner": "me"}, "unknown_fields"),
    ],
)
def test_create_rejects_bad_input(client, body, field):
    res = client.post("/tasks", json=body)
    assert res.status_code == 400
    assert field in res.get_json()["fields"]


def test_create_rejects_non_json(client):
    res = client.post("/tasks", data="title=hi")
    assert res.status_code == 400


# --- read -------------------------------------------------------------------

def test_get_one(client):
    task = make(client, title="Fix login bug")
    assert client.get(f"/tasks/{task['id']}").get_json()["title"] == "Fix login bug"


def test_get_missing_returns_json_404(client):
    res = client.get("/tasks/999")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Not Found"


def test_list_filters_by_status_and_priority(client):
    make(client, title="a", status="done", priority="high")
    make(client, title="b", status="todo", priority="high")
    make(client, title="c", status="todo", priority="low")
    res = client.get("/tasks?status=todo&priority=high").get_json()
    assert [t["title"] for t in res["items"]] == ["b"]
    assert res["total"] == 1


def test_list_search(client):
    make(client, title="Deploy API")
    make(client, title="Buy groceries")
    titles = [t["title"] for t in client.get("/tasks?q=api").get_json()["items"]]
    assert titles == ["Deploy API"]


def test_list_sorts_priority_by_importance(client):
    make(client, title="low", priority="low")
    make(client, title="high", priority="high")
    make(client, title="medium", priority="medium")
    titles = [t["title"] for t in client.get("/tasks?sort=priority").get_json()["items"]]
    assert titles == ["high", "medium", "low"]


def test_list_paginates(client):
    for i in range(5):
        make(client, title=f"task {i}")
    res = client.get("/tasks?per_page=2&page=3").get_json()
    assert res["total"] == 5
    assert [t["title"] for t in res["items"]] == ["task 4"]


def test_list_rejects_unknown_sort(client):
    # Guards against SQL injection through the ORDER BY clause.
    res = client.get("/tasks?sort=id;DROP TABLE tasks")
    assert res.status_code == 400


# --- update -----------------------------------------------------------------

def test_patch_changes_only_sent_fields(client):
    task = make(client, title="Draft", priority="low")
    res = client.patch(f"/tasks/{task['id']}", json={"status": "in_progress"})
    updated = res.get_json()
    assert updated["status"] == "in_progress"
    assert updated["priority"] == "low"
    assert updated["title"] == "Draft"


def test_patch_empty_body_rejected(client):
    task = make(client)
    assert client.patch(f"/tasks/{task['id']}", json={}).status_code == 400


def test_patch_missing_task(client):
    assert client.patch("/tasks/42", json={"status": "done"}).status_code == 404


def test_patch_can_clear_due_date(client):
    task = make(client, due_date="2026-12-01")
    res = client.patch(f"/tasks/{task['id']}", json={"due_date": None})
    assert res.get_json()["due_date"] is None


# --- delete -----------------------------------------------------------------

def test_delete(client):
    task = make(client)
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404


# --- stats ------------------------------------------------------------------

def test_stats_counts_and_overdue(client):
    make(client, title="old", due_date="2020-01-01")
    make(client, title="old but done", due_date="2020-01-01", status="done")
    make(client, title="future", due_date="2999-01-01", priority="high")
    stats = client.get("/tasks/stats").get_json()
    assert stats["total"] == 3
    assert stats["overdue"] == 1
    assert stats["by_status"] == {"todo": 2, "in_progress": 0, "done": 1}
    assert stats["by_priority"]["high"] == 1


# --- validation unit tests --------------------------------------------------

def test_validate_partial_allows_missing_title():
    assert validate_task({"status": "done"}, partial=True) == {"status": "done"}


def test_validate_normalises_date():
    assert validate_task({"title": "t", "due_date": "2026-01-05"})["due_date"] == "2026-01-05"


def test_validate_rejects_list_body():
    with pytest.raises(ValidationError):
        validate_task([1, 2])
