"""
init_db.py
CampusConnect - Database Initialization Script

Creates a clean SQLite database (database.db) with four tables:
Users, Events, Registrations, Messages.

The Events table includes an 'image' column that stores the filename
of an uploaded event image (saved under static/uploads/ by app.py).
If no image is uploaded, app.py falls back to 'default-event.jpg'.

Run this file once to set up (or reset) the database:
    python init_db.py
"""

import sqlite3
import os

DATABASE_NAME = "database.db"
DEFAULT_EVENT_IMAGE = "default-event.jpg"


def create_connection():
    """Create and return a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables(conn):
    """Create all required tables for CampusConnect."""
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # USERS TABLE
    # Stores both Student and Company accounts, distinguished by 'role'.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student', 'company')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # EVENTS TABLE
    # Events are created by Company users.
    # 'image' stores the filename of the uploaded event image
    # (located in static/uploads/). Defaults to 'default-event.jpg'
    # when no image is uploaded.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            capacity INTEGER,
            event_date TEXT NOT NULL,
            location TEXT,
            image TEXT DEFAULT 'default-event.jpg',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES Users (id) ON DELETE CASCADE
        )
    """)

    # ------------------------------------------------------------------
    # REGISTRATIONS TABLE
    # Students register for Events. A student can only register once
    # per event (enforced by UNIQUE constraint).
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES Events (id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES Users (id) ON DELETE CASCADE,
            UNIQUE (event_id, student_id)
        )
    """)

    # ------------------------------------------------------------------
    # MESSAGES TABLE
    # Direct messages between Students and Companies.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES Users (id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES Users (id) ON DELETE CASCADE
        )
    """)

    conn.commit()


def ensure_upload_folder():
    """
    Make sure static/uploads/ exists so image uploads and the
    default event image fallback both work correctly.
    """
    upload_folder = os.path.join("static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    default_image_path = os.path.join(upload_folder, DEFAULT_EVENT_IMAGE)
    if not os.path.exists(default_image_path):
        print(f"NOTE: '{default_image_path}' does not exist yet.")
        print("Add a default-event.jpg placeholder image there so events "
              "without an uploaded image display correctly.")


def main():
    # Remove old database file for a clean start (optional safety step)
    if os.path.exists(DATABASE_NAME):
        print(f"Existing '{DATABASE_NAME}' found. Recreating fresh database...")
        os.remove(DATABASE_NAME)

    conn = create_connection()
    try:
        create_tables(conn)
        print("Database initialized successfully.")
        print("Tables created: Users, Events, Registrations, Messages")
    finally:
        conn.close()

    ensure_upload_folder()


if __name__ == "__main__":
    main()