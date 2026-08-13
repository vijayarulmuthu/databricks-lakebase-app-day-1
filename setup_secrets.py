"""
One-time setup script: creates the Databricks secret scope and stores the
Massive API key. Run this locally (with the Databricks CLI configured) or
from a notebook - never commit the resulting secret value anywhere.

Usage:
    python setup_secrets.py
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

w = WorkspaceClient()

w.secrets.create_scope(scope="vj-massive")
w.secrets.put_secret(
    scope="vj-massive",
    key="api-key",
    string_value=getpass.getpass("Paste your Massive API key: ")
)

w.secrets.create_scope(scope="vj-database")
w.secrets.put_secret(
    scope="vj-database",
    key="lakebase-url",
    string_value=getpass.getpass("Paste your Lakebase URL: ")
)


w.secrets.put_acl(
    scope="vj-database",
    principal="users",
    permission=workspace.AclPermission.READ,
)

w.secrets.put_acl(
    scope="vj-massive",
    principal="users",
    permission=workspace.AclPermission.READ,
)
