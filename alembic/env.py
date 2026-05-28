import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from ytclfr.db.base import Base
import ytclfr.db.models.job
import ytclfr.db.models.router_decision
import ytclfr.db.models.signal_manifest  # V2 Stage A
import ytclfr.db.models.evidence_graph  # V2 Stage C
import ytclfr.db.models.v3.v3_evidence_graphs   # V3 Stage C
import ytclfr.db.models.v3.v3_extractor_bundles  # V3 Stage B
import ytclfr.db.models.aligned_segment
from pgvector.sqlalchemy import Vector

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from ytclfr.core.config import get_settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
