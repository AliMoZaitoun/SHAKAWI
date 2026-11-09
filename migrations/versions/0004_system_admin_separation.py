"""Move technical administration off the governor role."""
from alembic import op
from sqlalchemy import inspect

revision = "0004_system_admin"
down_revision = "0003_directorate_hierarchy"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    tables = set(inspect(connection).get_table_names())
    if not {"roles", "role_permissions"}.issubset(tables):
        return
    # Preserve the governor's global complaint operations, but require the
    # dedicated system_admin role for technical administration and ID files.
    connection.exec_driver_sql(
        """
        DELETE FROM role_permissions
        WHERE role_id = (SELECT id FROM roles WHERE code = 'governor')
          AND permission_code IN (
            'rbac.manage',
            'employees.manage',
            'directorates.manage',
            'audit.view',
            'files.identity.read'
          )
        """
    )


def downgrade():
    raise RuntimeError(
        "Destructive downgrade disabled. Restore a verified database backup; "
        "do not silently restore technical administration to the governor role."
    )
