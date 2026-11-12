"""Input validation for task payloads.

Kept separate from the routes so the rules are easy to read and unit test.
"""

from datetime import date

STATUSES = ("todo", "in_progress", "done")
PRIORITIES = ("low", "medium", "high")
MAX_TITLE = 200
MAX_DESCRIPTION = 2000


class ValidationError(ValueError):
    """Raised with a dict of field -> problem when a payload is invalid."""

    def __init__(self, errors):
        super().__init__("invalid task payload")
        self.errors = errors


def validate_task(payload, partial=False):
    """Check a task payload and return only the clean, known fields.

    partial=True is used for PATCH, where every field is optional but
    whatever is sent must still be valid.
    """
    if not isinstance(payload, dict):
        raise ValidationError({"body": "Send a JSON object."})

    errors = {}
    clean = {}

    if "title" in payload or not partial:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            errors["title"] = "Title is required."
        elif len(title) > MAX_TITLE:
            errors["title"] = f"Title must be {MAX_TITLE} characters or fewer."
        else:
            clean["title"] = title.strip()

    if "description" in payload:
        desc = payload["description"]
        if not isinstance(desc, str):
            errors["description"] = "Description must be text."
        elif len(desc) > MAX_DESCRIPTION:
            errors["description"] = f"Description must be {MAX_DESCRIPTION} characters or fewer."
        else:
            clean["description"] = desc

    if "status" in payload:
        if payload["status"] not in STATUSES:
            errors["status"] = f"Status must be one of: {', '.join(STATUSES)}."
        else:
            clean["status"] = payload["status"]

    if "priority" in payload:
        if payload["priority"] not in PRIORITIES:
            errors["priority"] = f"Priority must be one of: {', '.join(PRIORITIES)}."
        else:
            clean["priority"] = payload["priority"]

    if "due_date" in payload:
        due = payload["due_date"]
        if due is None:
            clean["due_date"] = None
        else:
            try:
                clean["due_date"] = date.fromisoformat(str(due)).isoformat()
            except ValueError:
                errors["due_date"] = "Due date must look like YYYY-MM-DD."

    unknown = set(payload) - {"title", "description", "status", "priority", "due_date"}
    if unknown:
        errors["unknown_fields"] = f"Not allowed: {', '.join(sorted(unknown))}."

    if partial and not clean and not errors:
        errors["body"] = "Send at least one field to update."

    if errors:
        raise ValidationError(errors)
    return clean
