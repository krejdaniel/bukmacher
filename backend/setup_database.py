
import getpass
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

db_host = os.getenv("DB_HOST") or "localhost"
db_port = os.getenv("DB_PORT") or "5432"
db_name = os.getenv("DB_NAME") or "football_predictor"
db_user = os.getenv("DB_USER") or "postgres"
db_password = os.getenv("DB_PASSWORD") or ""

if not db_password:
    db_password = getpass.getpass(
        f"Podaj hasło PostgreSQL dla użytkownika {db_user}: "
    )

    if not db_password:
        raise SystemExit("Hasło nie może być puste.")

    lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    found = False

    for i, line in enumerate(lines):
        if line.strip().startswith("DB_PASSWORD="):
            escaped = db_password.replace("\\", "\\\\").replace('"', '\\"')
            lines[i] = f'DB_PASSWORD="{escaped}"'
            found = True
            break

    if not found:
        escaped = db_password.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'DB_PASSWORD="{escaped}"')

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["DB_PASSWORD"] = db_password

print(f"Łączenie z PostgreSQL: {db_host}:{db_port}")

try:
    connection = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname="postgres",
        user=db_user,
        password=db_password,
        connect_timeout=10,
    )
    connection.autocommit = True

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,),
            )
            database_exists = cursor.fetchone() is not None

            if database_exists:
                print(f"Baza '{db_name}' już istnieje — pozostawiam ją bez zmian.")
            else:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(db_name)
                    )
                )
                print(f"Utworzono bazę '{db_name}'.")

    finally:
        connection.close()

except Exception as exc:
    raise SystemExit(
        "\nNie udało się utworzyć lub sprawdzić bazy PostgreSQL.\n"
        "Sprawdź, czy PostgreSQL działa, oraz ustawienia DB_HOST, DB_PORT, "
        "DB_NAME, DB_USER i DB_PASSWORD w backend\\.env.\n"
        f"Szczegóły: {exc}"
    )
