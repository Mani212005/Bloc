"""
conftest.py — SQLite-compatible test setup.

The app uses PostgreSQL-specific column types (ARRAY, JSONB, native Uuid, Enum).
This module patches those types before any app code is imported so the ORM
mapper compiles with SQLite-friendly equivalents.  Once patched, all ORM
operations (INSERT, SELECT, flush, refresh, db.get) work transparently.
"""
import json
import sys
import uuid as _uuid_mod

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Build SQLite-compatible TypeDecorators
# ─────────────────────────────────────────────────────────────────────────────
from sqlalchemy import String, Text, types


class _TextEnum(types.TypeDecorator):
    """Store an Enum by its .value (lowercase string) in SQLite TEXT."""
    impl = String(32)
    cache_ok = True

    def __init__(self, enum_class=None, *args, **kwargs):
        super().__init__()
        self._enum_class = enum_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # Accept both enum instance and raw string
        return value.value if hasattr(value, "value") else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if self._enum_class is not None:
            # look up by value (e.g. 'active' → CallerStatus.ACTIVE)
            try:
                return self._enum_class(value)
            except ValueError:
                pass
        return value


class _JsonArray(types.TypeDecorator):
    """Store a list as JSON string in SQLite TEXT."""
    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__()

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else "[]"

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return value if isinstance(value, list) else json.loads(value)


class _JsonObject(types.TypeDecorator):
    """Store a dict as JSON string in SQLite TEXT."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, dict) else json.loads(value)


class _UuidStr(types.TypeDecorator):
    """Store uuid.UUID as a 36-char dash-separated string in SQLite TEXT.

    Replaces both ``sqlalchemy.dialects.postgresql.UUID`` and the built-in
    ``sqlalchemy.types.Uuid`` so that every UUID column works on SQLite.
    """
    impl = String(36)
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)  # always '550e8400-e29b-41d4-a716-...'

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, _uuid_mod.UUID) else _uuid_mod.UUID(str(value))


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Patch sqlalchemy internals BEFORE any app module is imported
# ─────────────────────────────────────────────────────────────────────────────

# 2a. Replace the built-in Uuid type used by Mapped[uuid.UUID]
import sqlalchemy.types as _sa_types
import sqlalchemy as _sa

_sa_types.Uuid = _UuidStr
_sa.Uuid = _UuidStr

# Also patch the internal registry that maps Python types → SA column types
# so that ``Mapped[uuid.UUID]`` resolves to _UuidStr instead of Uuid()
from sqlalchemy.orm import decl_api as _decl_api  # noqa
_type_map = getattr(_decl_api, "_type_map", None) or getattr(_sa_types, "_type_map", {})
if _uuid_mod.UUID in _type_map:
    _type_map[_uuid_mod.UUID] = _UuidStr()

# 2b. Replace postgresql-specific types
from types import ModuleType as _ModuleType
import sqlalchemy.dialects.postgresql as _real_pg

_pg_shim = _ModuleType("sqlalchemy.dialects.postgresql")
_pg_shim.__dict__.update(_real_pg.__dict__)
_pg_shim.UUID = _UuidStr
_pg_shim.ARRAY = _JsonArray
_pg_shim.JSONB = _JsonObject
sys.modules["sqlalchemy.dialects.postgresql"] = _pg_shim

import sqlalchemy.dialects as _dialects
_dialects.postgresql = _pg_shim

# 2c. Patch the Enum constructor used in models.py so it stores by value
import sqlalchemy as _sqla
_OrigEnum = _sqla.Enum


class _ValueEnum(_OrigEnum):
    """SQLAlchemy Enum variant that stores the .value string, not .name."""

    def __init__(self, *enums, **kw):
        # Extract enum class if passed as single arg
        if len(enums) == 1 and isinstance(enums[0], type) and issubclass(
            enums[0], _uuid_mod.__class__  # any class
        ):
            self._enum_class = enums[0]
        else:
            self._enum_class = None
        # Build a TextEnum-based column instead of a real SA Enum
        # We'll swap ourselves out with _TextEnum
        super().__init__(*enums, **kw)

    def _resolve_for_literal(self, value):
        return value.value if hasattr(value, "value") else value


# 2d. Patch the mapper type resolver for uuid.UUID
try:
    from sqlalchemy.orm.decl_api import _resolve_type as _orig_resolve
    def _patched_resolve(python_type, *a, **kw):
        if python_type is _uuid_mod.UUID:
            return _UuidStr()
        return _orig_resolve(python_type, *a, **kw)
    import sqlalchemy.orm.decl_api as _decl
    _decl._resolve_type = _patched_resolve
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# 3.  NOW import app modules (they will pick up the patched types)
# ─────────────────────────────────────────────────────────────────────────────

# Force-reload models so the patched pg types are baked into the mapper
for _mod in list(sys.modules.keys()):
    if _mod.startswith("app."):
        del sys.modules[_mod]

from app.database import Base, get_db  # noqa: E402
import app.models  # noqa: F401
from app.main import app  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# 4.  Patch Enum columns on already-compiled mappers
# ─────────────────────────────────────────────────────────────────────────────
# Even after re-import, SQLAlchemy Enum still uses names not values.
# Replace every Enum column type on the table metadata with _TextEnum.
from sqlalchemy import event as _sa_event
from app.models import CallerStatus, LeadAssignmentStatus

_ENUM_MAP = {
    "caller_status": CallerStatus,
    "lead_assignment_status": LeadAssignmentStatus,
}

for _table in Base.metadata.tables.values():
    for _col in _table.columns:
        if isinstance(_col.type, _sa_types.Enum):
            _enum_name = getattr(_col.type, "name", None)
            _enum_cls = _ENUM_MAP.get(_enum_name)
            _col.type = _TextEnum(_enum_cls)

# ─────────────────────────────────────────────────────────────────────────────
# 5.  Create the SQLite test engine + fixtures
# ─────────────────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_db():
    """Truncate all tables between tests."""
    with _engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())
    yield


@pytest.fixture
def db():
    session = _Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
