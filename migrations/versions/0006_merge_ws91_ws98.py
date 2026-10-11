"""Join the user-name and customer-address migration histories."""

revision = "0006_merge_ws91_ws98"
down_revision = ("0004_user_names_terms", "0005_customer_addresses")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
