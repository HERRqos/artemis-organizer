"""Persistent client records in Postgres.
    session.py only remembers the last 12h of a conversation; this is where
    "who is this phone number" actually lives — across days, not hours.
"""
import psycopg2
import psycopg2.extras

class ClientStore:
    def __init__(self,database_url:str):
        self._url=database_url
        self._ensure_table()

    def _connect(self):
        return psycopg2.connect(self._url)

    def _ensure_table(self)->None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    phone_number TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    active_appointment TIMESTAMPTZ,
                    last_appointment TIMESTAMPTZ,
                    escalated_at TIMESTAMPTZ
                );
                ALTER TABLE clients ADD COLUMN IF NOT EXISTS email TEXT
                """
            )
            conn.commit()

    def get(self, phone_number: str) -> dict | None:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM clients WHERE phone_number = %s", (phone_number,))
            return cur.fetchone()

    def upsert_name(self, phone_number: str, name: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (phone_number, name) VALUES (%s, %s)
                ON CONFLICT (phone_number) DO UPDATE SET name = EXCLUDED.name
                """,
                (phone_number, name),
            )
            conn.commit()

    def upsert_email(self, phone_number: str, email: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (phone_number, email) VALUES (%s, %s)
                ON CONFLICT (phone_number) DO UPDATE SET email = EXCLUDED.email
                """,
                (phone_number, email),
            )
            conn.commit()

    def set_active_appointment(self, phone_number: str, start) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (phone_number, active_appointment) VALUES (%s, %s)
                ON CONFLICT (phone_number) DO UPDATE SET active_appointment = EXCLUDED.active_appointment
                """,
                (phone_number, start),
            )
            conn.commit()

    def clear_active_appointment(self, phone_number: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE clients
                SET last_appointment = active_appointment, active_appointment = NULL
                WHERE phone_number = %s
                """,
                (phone_number,),
            )
            conn.commit()

    def mark_escalated(self, phone_number: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (phone_number, escalated_at) VALUES (%s, now())
                ON CONFLICT (phone_number) DO UPDATE SET escalated_at = now()
                """,
                (phone_number,),
            )
            conn.commit()  