# Task Tracker API

A REST API for managing to-do tasks, built with Python, Flask and SQLite.
It supports full create/read/update/delete, filtering, search, sorting,
pagination and summary stats, with input validation on every write.

![CI](https://github.com/ishkaranbrar47-gif/task-tracker-api/actions/workflows/ci.yml/badge.svg)

## Features

- **7 endpoints**: health check, list, create, read, update (partial), delete, stats
- **Validation**: required title, allowed statuses and priorities, ISO dates,
  length limits, and rejection of unknown fields, all returned as clear JSON errors
- **Querying**: filter by status and priority, search titles, sort by any of
  5 fields (priority sorts by importance, not A–Z), and paginate
- **Safe SQL**: every value is a bound parameter; sort columns come from an allow-list
- **Stats**: counts by status and priority, plus open tasks that are overdue
- **Tested**: 28 pytest tests, 95% code coverage
- **CI**: GitHub Actions runs linting (ruff) and the test suite on Python 3.11, 3.12 and 3.13
  for every push and pull request, and fails the build below 90% coverage

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                    # serves on http://127.0.0.1:5000
```

## Try it

```bash
# create
curl -X POST http://127.0.0.1:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Send invoice", "priority": "high", "due_date": "2026-12-01"}'

# list open high-priority tasks, most urgent first
curl "http://127.0.0.1:5000/tasks?status=todo&priority=high&sort=due_date"

# mark task 1 done
curl -X PATCH http://127.0.0.1:5000/tasks/1 \
  -H "Content-Type: application/json" -d '{"status": "done"}'

# summary
curl http://127.0.0.1:5000/tasks/stats
```

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/health` | Service status |
| GET | `/tasks` | List tasks. Query: `status`, `priority`, `q`, `sort`, `order`, `page`, `per_page` |
| POST | `/tasks` | Create a task. Body: `title` (required), `description`, `status`, `priority`, `due_date` |
| GET | `/tasks/<id>` | Get one task |
| PATCH | `/tasks/<id>` | Update only the fields you send |
| DELETE | `/tasks/<id>` | Delete a task |
| GET | `/tasks/stats` | Counts by status and priority, overdue count |

Statuses: `todo`, `in_progress`, `done`. Priorities: `low`, `medium`, `high`.

## Tests

```bash
pytest --cov=app --cov-report=term-missing
ruff check .
```

## Project layout

```
app/
  __init__.py     app factory, JSON error handler, health check
  db.py           SQLite connection per request, schema
  validation.py   payload rules, kept separate so they are easy to test
  routes.py       the /tasks endpoints
tests/
  test_api.py     endpoint and validation tests
.github/workflows/ci.yml
```
