"""Personal video history without permission restrictions or duplicated styles."""
from contextvars import ContextVar
import os

identity = ContextVar("tubeforge_member", default=None)


def current_owner():
    return (identity.get() or {}).get("username") or os.getenv("TUBEFORGE_DEFAULT_OWNER", "admin")


def owner_of(project):
    return project.get("owner_id") or os.getenv("TUBEFORGE_DEFAULT_OWNER", "admin")


def personal_projects(projects, scope="mine"):
    return projects if scope == "team" else [p for p in projects if owner_of(p) == current_owner()]


def current_name():
    return (identity.get() or {}).get('display_name') or current_owner()
