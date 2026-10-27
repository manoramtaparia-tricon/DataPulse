import os
from urllib.parse import urlparse

from databricks import sql


def _clean_host(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    if raw.startswith("http"):
        return urlparse(raw).hostname
    return raw.split("?")[0]


def get_connection():
    return sql.connect(
        server_hostname=_clean_host(os.getenv("DATABRICKS_HOST")),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN"),
    )


def run_query(query: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return columns, rows
