from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db
from functools import wraps

app = Flask(__name__)
app.secret_key = "communitybridge-dev-secret-change-in-production"

URGENCY_ORDER = {"emergency": 0, "urgent": 1, "normal": 2}


# ---------- helpers ----------

def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()
    return user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    db.close()
    return dict(nav_categories=categories, current_user=current_user())


@app.template_filter("urgency_sort")
def urgency_sort_key(posts):
    return sorted(posts, key=lambda p: URGENCY_ORDER.get(p["urgency"], 3))


# ---------- public pages ----------

@app.route("/")
def index():
    db = get_db()
    emergencies = db.execute(
        "SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id "
        "WHERE p.urgency IN ('emergency','urgent') AND p.status = 'open' AND p.flagged = 0 "
        "ORDER BY CASE p.urgency WHEN 'emergency' THEN 0 ELSE 1 END, p.created_at DESC LIMIT 6"
    ).fetchall()
    recent_needs = db.execute(
        "SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id "
        "WHERE p.post_type = 'need' AND p.status = 'open' AND p.flagged = 0 ORDER BY p.created_at DESC LIMIT 6"
    ).fetchall()
    recent_offers = db.execute(
        "SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id "
        "WHERE p.post_type = 'offer' AND p.status = 'open' AND p.flagged = 0 ORDER BY p.created_at DESC LIMIT 6"
    ).fetchall()
    stats = {
        "resolved": db.execute("SELECT COUNT(*) c FROM posts WHERE status = 'resolved'").fetchone()["c"],
        "open": db.execute("SELECT COUNT(*) c FROM posts WHERE status = 'open'").fetchone()["c"],
        "neighbors": db.execute("SELECT COUNT(*) c FROM users WHERE is_admin = 0").fetchone()["c"],
        "responses": db.execute("SELECT COUNT(*) c FROM responses").fetchone()["c"],
    }
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    db.close()
    return render_template(
        "index.html", emergencies=emergencies, recent_needs=recent_needs,
        recent_offers=recent_offers, stats=stats, categories=categories,
    )


@app.route("/browse")
def browse():
    post_type = request.args.get("type", "")
    category_id = request.args.get("category", type=int)
    urgency = request.args.get("urgency", "")
    neighborhood = request.args.get("neighborhood", "").strip()
    q = request.args.get("q", "").strip()

    db = get_db()
    sql = """SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id
             WHERE p.status != 'resolved' AND p.flagged = 0"""
    params = []
    if post_type in ("need", "offer"):
        sql += " AND p.post_type = ?"
        params.append(post_type)
    if category_id:
        sql += " AND p.category_id = ?"
        params.append(category_id)
    if urgency:
        sql += " AND p.urgency = ?"
        params.append(urgency)
    if neighborhood:
        sql += " AND p.neighborhood LIKE ?"
        params.append(f"%{neighborhood}%")
    if q:
        sql += " AND (p.title LIKE ? OR p.description LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY CASE p.urgency WHEN 'emergency' THEN 0 WHEN 'urgent' THEN 1 ELSE 2 END, p.created_at DESC"

    posts = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    db.close()
    return render_template(
        "browse.html", posts=posts, categories=categories, post_type=post_type,
        category_id=category_id, urgency=urgency, neighborhood=neighborhood, q=q,
    )


@app.route("/post/<int:post_id>")
def post_detail(post_id):
    db = get_db()
    post = db.execute(
        "SELECT p.*, u.username, u.bio, u.skills, u.phone, u.email FROM posts p "
        "JOIN users u ON p.user_id = u.id WHERE p.id = ?", (post_id,)
    ).fetchone()
    if not post:
        db.close()
        flash("Post not found.", "danger")
        return redirect(url_for("browse"))
    responses = db.execute(
        "SELECT r.*, u.username, u.phone, u.email FROM responses r JOIN users u ON r.user_id = u.id "
        "WHERE r.post_id = ? ORDER BY r.created_at ASC", (post_id,)
    ).fetchall()
    thanks = db.execute(
        "SELECT t.*, u.username as from_username FROM thanks t JOIN users u ON t.from_user_id = u.id "
        "WHERE t.post_id = ? ORDER BY t.created_at DESC", (post_id,)
    ).fetchall()
    db.close()
    return render_template("post_detail.html", post=post, responses=responses, thanks=thanks)


@app.route("/post/new", methods=["GET", "POST"])
@login_required
def new_post():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    if request.method == "POST":
        user = current_user()
        db.execute(
            """INSERT INTO posts (user_id, post_type, category_id, title, description, neighborhood, urgency)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session["user_id"], request.form["post_type"], request.form.get("category_id", type=int),
                request.form["title"].strip(), request.form["description"].strip(),
                request.form.get("neighborhood", user["neighborhood"] or "").strip(),
                request.form.get("urgency", "normal"),
            ),
        )
        db.commit()
        db.close()
        flash("Your post is live. Thank you for strengthening the community!", "success")
        return redirect(url_for("browse"))
    db.close()
    default_type = request.args.get("type", "need")
    return render_template("new_post.html", categories=categories, default_type=default_type)


@app.route("/post/<int:post_id>/respond", methods=["POST"])
@login_required
def respond_to_post(post_id):
    message = request.form["message"].strip()
    db = get_db()
    db.execute(
        "INSERT INTO responses (post_id, user_id, message) VALUES (?, ?, ?)",
        (post_id, session["user_id"], message),
    )
    db.execute(
        "UPDATE posts SET status = 'in_progress' WHERE id = ? AND status = 'open'", (post_id,)
    )
    db.commit()
    db.close()
    flash("Response sent! Your contact details are now visible to the post author.", "success")
    return redirect(url_for("post_detail", post_id=post_id))


@app.route("/post/<int:post_id>/resolve", methods=["POST"])
@login_required
def resolve_post(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post or post["user_id"] != session["user_id"]:
        db.close()
        flash("You can only resolve your own posts.", "danger")
        return redirect(url_for("post_detail", post_id=post_id))
    db.execute("UPDATE posts SET status = 'resolved' WHERE id = ?", (post_id,))
    helper_username = request.form.get("helper_username", "").strip()
    thanks_message = request.form.get("thanks_message", "").strip()
    if helper_username:
        helper = db.execute("SELECT * FROM users WHERE username = ?", (helper_username,)).fetchone()
        if helper:
            db.execute(
                "INSERT INTO thanks (post_id, from_user_id, to_user_id, message) VALUES (?, ?, ?, ?)",
                (post_id, session["user_id"], helper["id"], thanks_message),
            )
            db.execute("UPDATE users SET impact_points = impact_points + 10 WHERE id = ?", (helper["id"],))
    db.commit()
    db.close()
    flash("Marked as resolved. Thanks for closing the loop!", "success")
    return redirect(url_for("post_detail", post_id=post_id))


# ---------- auth & profile ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        neighborhood = request.form.get("neighborhood", "").strip()
        db = get_db()
        existing = db.execute("SELECT 1 FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()
        if existing:
            db.close()
            flash("Username or email already registered.", "danger")
            return redirect(url_for("register"))
        db.execute(
            "INSERT INTO users (username, email, password_hash, neighborhood) VALUES (?, ?, ?, ?)",
            (username, email, generate_password_hash(password), neighborhood),
        )
        db.commit()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        session["user_id"] = user["id"]
        flash(f"Welcome to CommunityBridge, {username}! Consider adding your skills in your profile.", "success")
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form["identifier"].strip().lower()
        password = request.form["password"]
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE lower(username) = ? OR email = ?", (identifier, identifier)
        ).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "UPDATE users SET bio = ?, skills = ?, neighborhood = ?, phone = ? WHERE id = ?",
            (
                request.form.get("bio", "").strip(), request.form.get("skills", "").strip(),
                request.form.get("neighborhood", "").strip(), request.form.get("phone", "").strip(),
                session["user_id"],
            ),
        )
        db.commit()
        flash("Profile updated.", "success")
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    my_posts = db.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    my_responses = db.execute(
        "SELECT r.*, p.title, p.id as post_id FROM responses r JOIN posts p ON r.post_id = p.id "
        "WHERE r.user_id = ? ORDER BY r.created_at DESC", (session["user_id"],)
    ).fetchall()
    my_thanks = db.execute(
        "SELECT t.*, u.username as from_username FROM thanks t JOIN users u ON t.from_user_id = u.id "
        "WHERE t.to_user_id = ? ORDER BY t.created_at DESC", (session["user_id"],)
    ).fetchall()
    db.close()
    return render_template("profile.html", user=user, my_posts=my_posts, my_responses=my_responses, my_thanks=my_thanks)


# ---------- admin / moderation ----------

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "total_users": db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "total_posts": db.execute("SELECT COUNT(*) c FROM posts").fetchone()["c"],
        "open_emergencies": db.execute(
            "SELECT COUNT(*) c FROM posts WHERE urgency = 'emergency' AND status = 'open'"
        ).fetchone()["c"],
        "resolved": db.execute("SELECT COUNT(*) c FROM posts WHERE status = 'resolved'").fetchone()["c"],
    }
    flagged = db.execute(
        "SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id WHERE p.flagged = 1"
    ).fetchall()
    all_posts = db.execute(
        "SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id ORDER BY p.created_at DESC LIMIT 20"
    ).fetchall()
    db.close()
    return render_template("admin_dashboard.html", stats=stats, flagged=flagged, all_posts=all_posts)


@app.route("/admin/post/<int:post_id>/flag", methods=["POST"])
@admin_required
def admin_toggle_flag(post_id):
    db = get_db()
    post = db.execute("SELECT flagged FROM posts WHERE id = ?", (post_id,)).fetchone()
    db.execute("UPDATE posts SET flagged = ? WHERE id = ?", (0 if post["flagged"] else 1, post_id))
    db.commit()
    db.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/post/<int:post_id>/delete", methods=["POST"])
@admin_required
def admin_delete_post(post_id):
    db = get_db()
    db.execute("DELETE FROM responses WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM thanks WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    db.close()
    flash("Post removed.", "success")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5001, use_reloader=False)