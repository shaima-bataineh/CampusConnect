"""
app.py
CampusConnect - University Event Management Platform
Users: Student, Company
"""

import os
import sqlite3
from datetime import date
from functools import wraps

from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

DATABASE_NAME = "database.db"

# Number of upcoming events to show in the Home page "Featured Events" section
FEATURED_EVENTS_LIMIT = 4

app = Flask(__name__)
app.secret_key = "campusconnect-dev-secret-key"  # change in production

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DEFAULT_EVENT_IMAGE = "default-event.jpg"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the upload folder exists so image.save() never fails
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ----------------------------------------------------------------------
# DATABASE HELPERS
# ----------------------------------------------------------------------

def get_db():
    """Open a new database connection if none exists for the current context."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_NAME)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ----------------------------------------------------------------------
# IMAGE UPLOAD HELPER
# ----------------------------------------------------------------------

def allowed_file(filename):
    """Check the uploaded file has an allowed image extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_image(file_storage):
    """
    Save an uploaded image file to static/uploads using a secure filename.
    Returns the saved filename, or None if no valid file was uploaded.
    """
    if file_storage and file_storage.filename and allowed_file(file_storage.filename):
        filename = secure_filename(file_storage.filename)
        file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        return filename
    return None


# ----------------------------------------------------------------------
# AUTH HELPERS / DECORATORS
# ----------------------------------------------------------------------

def login_required(f):
    """Ensure a user is logged in before accessing a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    """Ensure the logged-in user has a specific role (student/company)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") != role:
                flash("You are not authorized to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user():
    """Return the full user row for the currently logged-in user."""
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute(
        "SELECT * FROM Users WHERE id = ?", (session["user_id"],)
    ).fetchone()


# ----------------------------------------------------------------------
# HOME
# ----------------------------------------------------------------------

@app.route("/")
def home():
    """
    Home page.
    Loads the latest upcoming events (from today onward) from SQLite to
    populate the Featured Events section.
    """
    db = get_db()
    today_str = date.today().isoformat()

    featured_events = db.execute(
        """
        SELECT Events.*, Users.name AS company_name
        FROM Events
        JOIN Users ON Users.id = Events.company_id
        WHERE Events.event_date >= ?
        ORDER BY Events.event_date ASC
        LIMIT ?
        """,
        (today_str, FEATURED_EVENTS_LIMIT),
    ).fetchall()

    return render_template("home.html", featured_events=featured_events)


# ----------------------------------------------------------------------
# STATIC INFO PAGES
# ----------------------------------------------------------------------

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not subject or not message:
            flash("Please fill in all fields before sending your message.", "danger")
            return redirect(url_for("contact"))

        # NOTE: no dedicated storage table for contact form submissions yet.
        # For now we simply acknowledge receipt of the message.
        flash("Your message has been sent. We'll get back to you soon!", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


# ----------------------------------------------------------------------
# STUDENT AUTH ROUTES
# ----------------------------------------------------------------------

@app.route("/student/auth")
def student_auth():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("student_auth.html")


@app.route("/student/login", methods=["POST"])
def student_login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    db = get_db()
    user = db.execute(
        "SELECT * FROM Users WHERE email = ? AND role = 'student'", (email,)
    ).fetchone()

    if user is None or not check_password_hash(user["password"], password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("student_auth"))

    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]

    flash(f"Welcome back, {user['name']}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/student/register", methods=["POST"])
def student_register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for("student_auth"))

    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("student_auth"))

    db = get_db()
    existing = db.execute("SELECT id FROM Users WHERE email = ?", (email,)).fetchone()

    if existing:
        flash("An account with this email already exists.", "danger")
        return redirect(url_for("student_auth"))

    hashed_password = generate_password_hash(password)
    db.execute(
        "INSERT INTO Users (name, email, password, role) VALUES (?, ?, ?, 'student')",
        (name, email, hashed_password),
    )
    db.commit()

    flash("Registration successful. Please log in.", "success")
    return redirect(url_for("student_auth"))


# ----------------------------------------------------------------------
# COMPANY AUTH ROUTES
# ----------------------------------------------------------------------

@app.route("/company/auth")
def company_auth():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("company_auth.html")


@app.route("/company/login", methods=["POST"])
def company_login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    db = get_db()
    user = db.execute(
        "SELECT * FROM Users WHERE email = ? AND role = 'company'", (email,)
    ).fetchone()

    if user is None or not check_password_hash(user["password"], password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("company_auth"))

    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]

    flash(f"Welcome back, {user['name']}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/company/register", methods=["POST"])
def company_register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for("company_auth"))

    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("company_auth"))

    db = get_db()
    existing = db.execute("SELECT id FROM Users WHERE email = ?", (email,)).fetchone()

    if existing:
        flash("An account with this email already exists.", "danger")
        return redirect(url_for("company_auth"))

    hashed_password = generate_password_hash(password)
    db.execute(
        "INSERT INTO Users (name, email, password, role) VALUES (?, ?, ?, 'company')",
        (name, email, hashed_password),
    )
    db.commit()

    flash("Registration successful. Please log in.", "success")
    return redirect(url_for("company_auth"))


# ----------------------------------------------------------------------
# LOGOUT
# ----------------------------------------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# ----------------------------------------------------------------------
# DASHBOARD
# ----------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    if session["role"] == "company":
        events = db.execute(
            "SELECT * FROM Events WHERE company_id = ? ORDER BY event_date ASC",
            (session["user_id"],),
        ).fetchall()
        return render_template("company_dashboard.html", events=events)

    else:  # student
        registrations = db.execute(
            """
            SELECT Events.*, Registrations.registered_at
            FROM Registrations
            JOIN Events ON Events.id = Registrations.event_id
            WHERE Registrations.student_id = ?
            ORDER BY Events.event_date ASC
            """,
            (session["user_id"],),
        ).fetchall()
        return render_template("student_dashboard.html", registrations=registrations)


# ----------------------------------------------------------------------
# EVENT ROUTES
# ----------------------------------------------------------------------

@app.route("/events")
def list_events():
    db = get_db()
    query = request.args.get("q", "").strip()

    if query:
        like_pattern = f"%{query}%"
        events = db.execute(
            """
            SELECT Events.*, Users.name AS company_name
            FROM Events
            JOIN Users ON Users.id = Events.company_id
            WHERE Events.title LIKE ?
               OR Events.description LIKE ?
               OR Users.name LIKE ?
            ORDER BY Events.event_date ASC
            """,
            (like_pattern, like_pattern, like_pattern),
        ).fetchall()
    else:
        events = db.execute(
            """
            SELECT Events.*, Users.name AS company_name
            FROM Events
            JOIN Users ON Users.id = Events.company_id
            ORDER BY Events.event_date ASC
            """
        ).fetchall()

    return render_template("events.html", events=events)


@app.route("/events/create", methods=["GET", "POST"])
@login_required
@role_required("company")
def create_event():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category")
        capacity = request.form.get("capacity")
        event_date = request.form.get("event_date", "").strip()
        location = request.form.get("location", "").strip()

        print("Capacity =", capacity) 
        if not title or not event_date:
            flash("Title and event date are required.", "danger")
            return redirect(url_for("create_event"))

        # Handle optional image upload; fall back to the default image
        uploaded_file = request.files.get("image")
        filename = save_uploaded_image(uploaded_file) or DEFAULT_EVENT_IMAGE

        db = get_db()
        db.execute(
            """
            INSERT INTO Events (company_id, title, description,category,capacity, event_date, location, image)
            VALUES (?, ?, ?, ?, ?, ?,?,?)
            """,
            (session["user_id"], title, description,category,capacity, event_date, location, filename),
        )
        db.commit()

        flash("Event created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_event.html")


@app.route("/events/<int:event_id>")
def view_event(event_id):
    db = get_db()
    event = db.execute(
        """
        SELECT Events.*, Users.name AS company_name, Users.email AS company_email
        FROM Events
        JOIN Users ON Users.id = Events.company_id
        WHERE Events.id = ?
        """,
        (event_id,),
    ).fetchone()

    if event is None:
        flash("Event not found.", "danger")
        return redirect(url_for("list_events"))

    already_registered = False
    if session.get("role") == "student":
        reg = db.execute(
            "SELECT id FROM Registrations WHERE event_id = ? AND student_id = ?",
            (event_id, session["user_id"]),
        ).fetchone()
        already_registered = reg is not None

    return render_template(
        "details.html", event=event, already_registered=already_registered
    )


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("company")
def edit_event(event_id):
    db = get_db()
    event = db.execute(
        "SELECT * FROM Events WHERE id = ? AND company_id = ?",
        (event_id, session["user_id"]),
    ).fetchone()

    if event is None:
        flash("Event not found or you do not have permission to edit it.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_date = request.form.get("event_date", "").strip()
        location = request.form.get("location", "").strip()

        if not title or not event_date:
            flash("Title and event date are required.", "danger")
            return redirect(url_for("edit_event", event_id=event_id))

        # Handle optional image upload; if no new image is provided,
        # keep the event's existing image instead of overwriting it.
        uploaded_file = request.files.get("image")
        new_filename = save_uploaded_image(uploaded_file)
        filename = new_filename if new_filename else event["image"]

        db.execute(
            """
            UPDATE Events
            SET title = ?, description = ?, event_date = ?, location = ?, image = ?
            WHERE id = ? AND company_id = ?
            """,
            (title, description, event_date, location, filename, event_id, session["user_id"]),
        )
        db.commit()

        flash("Event updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_event.html", event=event)


@app.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
@role_required("company")
def delete_event(event_id):
    db = get_db()
    db.execute(
        "DELETE FROM Events WHERE id = ? AND company_id = ?",
        (event_id, session["user_id"]),
    )
    db.commit()

    flash("Event deleted.", "info")
    return redirect(url_for("dashboard"))


# ----------------------------------------------------------------------
# REGISTRATION ROUTES
# ----------------------------------------------------------------------

@app.route("/events/<int:event_id>/register", methods=["POST"])
@login_required
@role_required("student")
def register_event(event_id):
    db = get_db()

    event = db.execute("SELECT id FROM Events WHERE id = ?", (event_id,)).fetchone()
    if event is None:
        flash("Event not found.", "danger")
        return redirect(url_for("list_events"))

    existing = db.execute(
        "SELECT id FROM Registrations WHERE event_id = ? AND student_id = ?",
        (event_id, session["user_id"]),
    ).fetchone()

    if existing:
        flash("You are already registered for this event.", "warning")
        return redirect(url_for("view_event", event_id=event_id))

    db.execute(
        "INSERT INTO Registrations (event_id, student_id) VALUES (?, ?)",
        (event_id, session["user_id"]),
    )
    db.commit()

    flash("Successfully registered for the event.", "success")
    return redirect(url_for("view_event", event_id=event_id))


@app.route("/events/<int:event_id>/unregister", methods=["POST"])
@login_required
@role_required("student")
def unregister_event(event_id):
    db = get_db()
    db.execute(
        "DELETE FROM Registrations WHERE event_id = ? AND student_id = ?",
        (event_id, session["user_id"]),
    )
    db.commit()

    flash("Registration cancelled.", "info")
    return redirect(url_for("view_event", event_id=event_id))


@app.route("/events/<int:event_id>/registrations")
@login_required
@role_required("company")
def view_registrations(event_id):
    db = get_db()

    event = db.execute(
        "SELECT * FROM Events WHERE id = ? AND company_id = ?",
        (event_id, session["user_id"]),
    ).fetchone()

    if event is None:
        flash("Event not found or you do not have permission to view this.", "danger")
        return redirect(url_for("dashboard"))

    registrations = db.execute(
        """
        SELECT Users.name, Users.email, Registrations.registered_at
        FROM Registrations
        JOIN Users ON Users.id = Registrations.student_id
        WHERE Registrations.event_id = ?
        ORDER BY Registrations.registered_at ASC
        """,
        (event_id,),
    ).fetchall()

    return render_template(
        "event_registrations.html", event=event, registrations=registrations
    )


# ----------------------------------------------------------------------
# MESSAGE ROUTES
# ----------------------------------------------------------------------

@app.route("/messages")
@login_required
def list_messages():
    db = get_db()

    conversations = db.execute(
        """
        SELECT DISTINCT Users.id, Users.name, Users.role
        FROM Messages
        JOIN Users ON Users.id = CASE
            WHEN Messages.sender_id = ? THEN Messages.receiver_id
            ELSE Messages.sender_id
        END
        WHERE Messages.sender_id = ? OR Messages.receiver_id = ?
        """,
        (session["user_id"], session["user_id"], session["user_id"]),
    ).fetchall()

    return render_template("messages_list.html", conversations=conversations)


@app.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
def conversation(user_id):
    db = get_db()

    other_user = db.execute("SELECT * FROM Users WHERE id = ?", (user_id,)).fetchone()
    if other_user is None:
        flash("User not found.", "danger")
        return redirect(url_for("list_messages"))

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            db.execute(
                "INSERT INTO Messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                (session["user_id"], user_id, content),
            )
            db.commit()
        return redirect(url_for("conversation", user_id=user_id))

    messages = db.execute(
        """
        SELECT * FROM Messages
        WHERE (sender_id = ? AND receiver_id = ?)
           OR (sender_id = ? AND receiver_id = ?)
        ORDER BY sent_at ASC
        """,
        (session["user_id"], user_id, user_id, session["user_id"]),
    ).fetchall()

    return render_template("conversation.html", messages=messages, other_user=other_user)


# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)