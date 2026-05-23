import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "pnr.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS flights (
                flight_no   TEXT NOT NULL,
                flight_date TEXT NOT NULL,
                origin      TEXT NOT NULL,
                destination TEXT NOT NULL,
                operator    TEXT,
                PRIMARY KEY (flight_no, flight_date, origin, destination)
            );
                           
            CREATE TABLE IF NOT EXISTS travel_documents (
                document_type   TEXT NOT NULL,
                document_no     TEXT NOT NULL,
                nationality     TEXT NOT NULL,
                last_name       TEXT NOT NULL,
                first_name      TEXT NOT NULL,
                date_of_birth   TEXT NOT NULL,
                country_of_issue TEXT NOT NULL,
                date_of_expiry  TEXT NOT NULL,
                PRIMARY KEY     (document_type, document_no)
            );

            CREATE TABLE IF NOT EXISTS passengers (
                id             INTEGER PRIMARY KEY,
                flight_no      TEXT NOT NULL,
                flight_date    TEXT NOT NULL,
                origin         TEXT NOT NULL,
                destination    TEXT NOT NULL,
                record_locator TEXT,
                last_name      TEXT NOT NULL,
                first_name     TEXT NOT NULL,
                title          TEXT,
                gender         TEXT,
                seat           TEXT,
                cabin_class    TEXT,
                fare_class     TEXT,
                e_ticket_no    TEXT,
                ssr_codes      TEXT,
                notes          TEXT,
                document_type  TEXT,
                document_no    TEXT,
                FOREIGN KEY (flight_no, flight_date, origin, destination)
                    REFERENCES  flights(flight_no, flight_date, origin, destination)
                FOREIGN KEY (document_type, document_no)
                    REFERENCES travel_documents(document_type, document_no)          
            );

            CREATE TABLE IF NOT EXISTS ssr_codes (
                code        TEXT PRIMARY KEY,
                description TEXT
            );
                           
            CREATE TRIGGER IF NOT EXISTS link_document_to_passenger
            AFTER INSERT ON travel_documents
            BEGIN
                UPDATE passengers
                SET document_type = NEW.document_type,
                    document_no = NEW.document_no
                WHERE last_name = NEW.last_name
                AND first_name = NEW.first_name;
            END;
                           
            CREATE TRIGGER IF NOT EXISTS update_document_reference
            AFTER UPDATE ON travel_documents
            BEGIN
                UPDATE passengers
                SET document_type = NEW.document_type,
                    document_no = NEW.document_no
                WHERE document_type = OLD.document_type
                AND document_no = OLD.document_no;
            END;
                           
            CREATE TRIGGER IF NOT EXISTS delete_document_reference
            AFTER DELETE ON travel_documents
            BEGIN
                UPDATE passengers
                SET document_type = NULL,
                    document_no = NULL
                WHERE document_type = OLD.document_type
                AND document_no = OLD.document_no;
            END;

            CREATE INDEX IF NOT EXISTS idx_passengers_cabin ON passengers(cabin_class);
            CREATE INDEX IF NOT EXISTS idx_passengers_ssr_codes ON passengers(ssr_codes);
        """)
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
