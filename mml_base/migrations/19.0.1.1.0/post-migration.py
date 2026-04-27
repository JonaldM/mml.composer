"""Post-migration for mml_base 19.0.1.1.0 — partial UNIQUE on mml.event.dedupe_key.

The 19.0.1.1.0 manifest bump adds a new ``dedupe_key`` column on
``mml.event``. The Odoo ORM creates the column and the (non-unique)
BTREE index automatically when the module is upgraded. This script then
adds a *partial* UNIQUE index that enforces uniqueness only when
``dedupe_key IS NOT NULL`` — legacy rows (created before this version)
are unaffected because they all carry NULL.

Why partial UNIQUE rather than ``UNIQUE NOT NULL``:
    - Existing rows must remain valid; we cannot retroactively assign
      keys without changing semantics.
    - Most events will continue to use ``emit()`` (no key); only
      callers that opt in via ``emit_idempotent()`` will populate it.

Why no CONCURRENTLY:
    Odoo migration scripts run inside a transaction. PostgreSQL forbids
    ``CREATE INDEX CONCURRENTLY`` inside a transaction (raises
    ``cannot run inside a transaction block``). The ``mml.event`` table
    is small in production (low hundreds of rows on a typical instance
    per the prem audit), so the brief lock is acceptable.

Manual rollback (if 19.0.1.1.0 must be reverted):
    DROP INDEX IF EXISTS mml_event_dedupe_key_uniq;
    ALTER TABLE mml_event DROP COLUMN IF EXISTS dedupe_key;
    -- then downgrade ir_module_module.latest_version manually
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add the partial UNIQUE index on ``mml_event.dedupe_key``.

    Args:
        cr: Odoo cursor (psycopg2 cursor wrapper).
        version: Module version string before the upgrade. ``None`` /
            empty string means a fresh install — in that case the ORM
            handles index creation alongside the column itself, so we
            do nothing here.
    """
    if not version:
        return
    cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
            mml_event_dedupe_key_uniq
            ON mml_event (dedupe_key)
            WHERE dedupe_key IS NOT NULL
    """)
    _logger.info(
        'mml_base 19.0.1.1.0: created partial UNIQUE index '
        'mml_event_dedupe_key_uniq on mml_event(dedupe_key) '
        'WHERE dedupe_key IS NOT NULL'
    )
