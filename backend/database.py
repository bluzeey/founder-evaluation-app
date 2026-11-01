import logging
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from workspace_context import current_user_id

from logger_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    """Convert legacy postgres:// URLs to SQLAlchemy-compatible postgresql+psycopg2://."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize_database_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://localhost:5432/founderos",
    )
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class WorkspaceSession(Session):
    """A business session belongs to exactly one verified workspace."""
    def __init__(self, *args, **kwargs):
        self.workspace_user_id = current_user_id()
        super().__init__(*args, **kwargs)

    def _assert_workspace(self):
        if current_user_id() != self.workspace_user_id:
            raise RuntimeError("Database session belongs to a different workspace")

    def get(self, *args, **kwargs):
        self._assert_workspace()
        return super().get(*args, **kwargs)

    def _get_impl(self, *args, **kwargs):
        self._assert_workspace()  # Includes legacy Query.get identity-map hits.
        return super()._get_impl(*args, **kwargs)

    def _execute_internal(self, *args, **kwargs):
        self._assert_workspace()  # Includes scalar/scalars and existing transactions.
        return super()._execute_internal(*args, **kwargs)

    def execute(self, *args, **kwargs):
        self._assert_workspace()
        return super().execute(*args, **kwargs)

    def query(self, *args, **kwargs):
        self._assert_workspace()
        return super().query(*args, **kwargs)

    def flush(self, *args, **kwargs):
        self._assert_workspace()
        return super().flush(*args, **kwargs)

    def add(self, *args, **kwargs):
        self._assert_workspace()
        return super().add(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._assert_workspace()
        return super().delete(*args, **kwargs)

    def merge(self, *args, **kwargs):
        self._assert_workspace()
        return super().merge(*args, **kwargs)

    def connection(self, *args, **kwargs):
        self._assert_workspace()
        return super().connection(*args, **kwargs)


@event.listens_for(WorkspaceSession, "after_begin")
def _select_workspace(session, transaction, connection):
    from private_workspaces import workspace_schema, role_for_user
    session._assert_workspace()
    if transaction.nested:
        return  # The outer transaction already selected this identity and role.
    schema = workspace_schema(connection, session.workspace_user_id)
    quote = connection.dialect.identifier_preparer.quote
    # SET LOCAL resets at transaction end; no pooled connection retains a user.
    # ORM SQL is schema-qualified; legacy textual SQL uses this closed path.
    connection.execute(text("SELECT set_config('search_path', :path, true)"),
                       {"path": "pg_catalog," + quote(schema) + ",pg_temp"})
    connection.exec_driver_sql("SET LOCAL ROLE " + quote(role_for_user(connection, session.workspace_user_id)))
    connection.execution_options(schema_translate_map={None: schema})


SessionLocal = sessionmaker(class_=WorkspaceSession, autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables. Useful for local dev; production should use Alembic."""
    logger.info("database.create_tables.start")
    Base.metadata.create_all(bind=engine)
    logger.info("database.create_tables.end")
