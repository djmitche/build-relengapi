"""add badpenny task summary

Revision ID: 2de009660da3
Revises: 993e4d841aa
Create Date: 2015-07-29 15:32:18.493404

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2de009660da3'
down_revision = '993e4d841aa'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('badpenny_tasks', sa.Column('summary', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('badpenny_tasks', 'summary')
