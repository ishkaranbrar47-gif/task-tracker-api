"""HTTP endpoints for tasks."""

from flask import Blueprint, abort, jsonify, request

from .db import get_db
from .validation import PRIORITIES, STATUSES, ValidationError, validate_task

bp = Blueprint("tasks", __name__, url_prefix="/tasks")

SORTABLE = {"created_at", "updated_at", "due_date", "priority", "title"}
# Sort priority by importance, not alphabetically.
PRIORITY_ORDER = "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"


def row_to_dict(row):
    return dict(row) if row else None


def fetch_task(task_id):
    row = get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        abort(404, description=f"No task with id {task_id}.")
    return row_to_dict(row)


def bad_request(errors):
    return jsonify(error="Bad Request", fields=errors), 400


@bp.get("")
def list_tasks():
    """List tasks with optional filters, sorting and pagination.

    Query params: status, priority, q (search in title), sort, order,
    page (from 1), per_page (1-100).
    """
    where, params = [], []

    status = request.args.get("status")
    if status:
        if status not in STATUSES:
            return bad_request({"status": f"Status must be one of: {', '.join(STATUSES)}."})
        where.append("status = ?")
        params.append(status)

    priority = request.args.get("priority")
    if priority:
        if priority not in PRIORITIES:
            return bad_request({"priority": f"Priority must be one of: {', '.join(PRIORITIES)}."})
        where.append("priority = ?")
        params.append(priority)

    q = request.args.get("q")
    if q:
        where.append("title LIKE ?")
        params.append(f"%{q}%")

    sort = request.args.get("sort", "created_at")
    if sort not in SORTABLE:
        return bad_request({"sort": f"Sort must be one of: {', '.join(sorted(SORTABLE))}."})
    order = "DESC" if request.args.get("order", "asc").lower() == "desc" else "ASC"
    sort_sql = PRIORITY_ORDER if sort == "priority" else sort

    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)
    except ValueError:
        return bad_request({"page": "page and per_page must be whole numbers."})

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    conn = get_db()
    total = conn.execute(f"SELECT COUNT(*) FROM tasks {where_sql}", params).fetchone()[0]
    # sort_sql and order come from fixed allow-lists above, never from raw input.
    rows = conn.execute(
        f"SELECT * FROM tasks {where_sql} ORDER BY {sort_sql} {order}, id ASC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()

    return jsonify(
        items=[row_to_dict(r) for r in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


@bp.post("")
def create_task():
    try:
        data = validate_task(request.get_json(silent=True))
    except ValidationError as err:
        return bad_request(err.errors)

    columns = ", ".join(data)
    placeholders = ", ".join("?" for _ in data)
    conn = get_db()
    cur = conn.execute(f"INSERT INTO tasks ({columns}) VALUES ({placeholders})", list(data.values()))
    conn.commit()
    task = fetch_task(cur.lastrowid)
    return jsonify(task), 201, {"Location": f"/tasks/{task['id']}"}


@bp.get("/<int:task_id>")
def get_task(task_id):
    return jsonify(fetch_task(task_id))


@bp.patch("/<int:task_id>")
def update_task(task_id):
    fetch_task(task_id)  # 404 before validating, so the error is accurate
    try:
        data = validate_task(request.get_json(silent=True), partial=True)
    except ValidationError as err:
        return bad_request(err.errors)

    assignments = ", ".join(f"{col} = ?" for col in data)
    conn = get_db()
    conn.execute(
        f"UPDATE tasks SET {assignments}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
        [*data.values(), task_id],
    )
    conn.commit()
    return jsonify(fetch_task(task_id))


@bp.delete("/<int:task_id>")
def delete_task(task_id):
    fetch_task(task_id)
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return "", 204


@bp.get("/stats")
def stats():
    """Counts by status and priority, plus how many open tasks are overdue."""
    conn = get_db()
    by_status = {s: 0 for s in STATUSES}
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"):
        by_status[row["status"]] = row["n"]
    by_priority = {p: 0 for p in PRIORITIES}
    for row in conn.execute("SELECT priority, COUNT(*) AS n FROM tasks GROUP BY priority"):
        by_priority[row["priority"]] = row["n"]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status != 'done' AND due_date IS NOT NULL AND due_date < date('now')"
    ).fetchone()[0]
    return jsonify(by_status=by_status, by_priority=by_priority, overdue=overdue, total=sum(by_status.values()))
