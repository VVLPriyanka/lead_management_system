import os
import re
import json
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template

from dotenv import load_dotenv
load_dotenv()

try:
    import anthropic
    _anthropic_available = True
except ImportError:
    _anthropic_available = False

app = Flask(__name__)
DB_PATH = "leads.db"


# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    NOT NULL,
                phone         TEXT    NOT NULL,
                business_type TEXT    NOT NULL,
                message       TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'New',
                created_at    TEXT    NOT NULL
            )
        """)
        conn.commit()


# ─────────────────────────────────────────
# VALIDATION HELPERS
# ─────────────────────────────────────────

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'
    return re.match(pattern, email) is not None


def is_valid_phone(phone):
    pattern = r'^[\+\d][\d\s\-\(\)]{7,15}$'
    return re.match(pattern, phone) is not None


def validate_lead(data):
    errors = []
    required_fields = ["name", "email", "phone", "business_type", "message"]

    for field in required_fields:
        if not data.get(field, "").strip():
            errors.append(f"{field.replace('_', ' ').title()} is required.")

    if data.get("email") and not is_valid_email(data["email"]):
        errors.append("Please enter a valid email address.")

    if data.get("phone") and not is_valid_phone(data["phone"]):
        errors.append("Please enter a valid phone number.")

    return errors


# ─────────────────────────────────────────
# EMAIL — ADMIN NOTIFICATION VIA RESEND
# ─────────────────────────────────────────

def send_admin_notification(lead_name, lead_email, lead_phone, business_type, message):
    """
    Send a lead notification email to the admin (YOU) via Resend API.
    Works on Render — no SMTP port restrictions.

    Required env vars:
        RESEND_API_KEY   — your Resend API key (re_xxxxxxxxxxxx)
        ADMIN_EMAIL      — the email that receives notifications (vvlpriyanka@gmail.com)
    """
    api_key     = os.environ.get("RESEND_API_KEY")
    admin_email = os.environ.get("ADMIN_EMAIL", "vvlpriyanka@gmail.com")

    if not api_key:
        print("[Email] Skipped — RESEND_API_KEY not set.")
        return

    subject = f"🔔 New Lead from {lead_name} — LeadFlow"

    body = f"""Hi Priyanka,

You have a new lead submission on LeadFlow!

─────────────────────────────
  Name          : {lead_name}
  Email         : {lead_email}
  Phone         : {lead_phone}
  Business Type : {business_type}
─────────────────────────────

Their Message:
{message}

─────────────────────────────
Go to your dashboard to view and respond:
http://localhost:5000/dashboard

— LeadFlow Notifications
"""

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from":    "LeadFlow <onboarding@resend.dev>",
                "to":      [admin_email],          # sends to YOU — works without a custom domain
                "subject": subject,
                "text":    body,
            },
            timeout=10,
        )

        if response.status_code == 200:
            print(f"[Email] Admin notification sent to {admin_email}")
        else:
            print(f"[Email] Resend error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"[Email] Failed to send notification: {e}")


def notify_n8n(lead_data):
    webhook_url = os.environ.get("N8N_WEBHOOK_URL")
    if not webhook_url:
        print("[n8n] Skipped — N8N_WEBHOOK_URL not set.")
        return
    try:
        requests.post(webhook_url, json=lead_data, timeout=5)
        print("[n8n] Lead sent to Google Sheets via n8n")
    except Exception as e:
        print(f"[n8n] Failed: {e}")


# ─────────────────────────────────────────
# ROUTES — PAGES
# ─────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ─────────────────────────────────────────
# ROUTES — API
# ─────────────────────────────────────────

@app.route("/api/leads", methods=["POST"])
def create_lead():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received."}), 400

    clean = {k: v.strip() if isinstance(v, str) else v for k, v in data.items()}

    errors = validate_lead(clean)
    if errors:
        return jsonify({"errors": errors}), 422

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO leads (name, email, phone, business_type, message, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'New', ?)""",
            (clean["name"], clean["email"], clean["phone"],
             clean["business_type"], clean["message"], created_at)
        )
        conn.commit()
        lead_id = cursor.lastrowid

    # Notify admin (you) — works on Render without a custom domain
    send_admin_notification(
        clean["name"], clean["email"], clean["phone"],
        clean["business_type"], clean["message"]
    )

    notify_n8n({
        "name":          clean["name"],
        "email":         clean["email"],
        "phone":         clean["phone"],
        "business_type": clean["business_type"],
        "message":       clean["message"],
        "created_at":    created_at,
    })

    return jsonify({
        "message": "Lead submitted successfully!",
        "id":      lead_id
    }), 201


@app.route("/api/leads", methods=["GET"])
def get_leads():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    query  = "SELECT * FROM leads WHERE 1=1"
    params = []

    if search:
        query += """ AND (
            name          LIKE ? OR
            email         LIKE ? OR
            phone         LIKE ? OR
            business_type LIKE ? OR
            message       LIKE ?
        )"""
        like = f"%{search}%"
        params.extend([like, like, like, like, like])

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at ASC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    leads = [dict(row) for row in rows]
    return jsonify(leads), 200


@app.route("/api/leads/<int:lead_id>/status", methods=["PATCH"])
def update_status(lead_id):
    data   = request.get_json()
    status = data.get("status", "").strip() if data else ""

    allowed = {"New", "Contacted", "Closed"}
    if status not in allowed:
        return jsonify({"error": f"Status must be one of: {', '.join(allowed)}"}), 422

    with get_db() as conn:
        result = conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?", (status, lead_id)
        )
        conn.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Lead not found."}), 404

    return jsonify({"message": "Status updated.", "id": lead_id, "status": status}), 200


@app.route("/api/stats", methods=["GET"])
def get_stats():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM leads GROUP BY status"
        ).fetchall()

    counts = {"Total": 0, "New": 0, "Contacted": 0, "Closed": 0}
    for row in rows:
        counts[row["status"]] = row["count"]
        counts["Total"] += row["count"]

    return jsonify(counts), 200


@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    with get_db() as conn:
        result = conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Lead not found."}), 404

    return jsonify({"message": "Lead deleted.", "id": lead_id}), 200


# ─────────────────────────────────────────
# AI / TEMPLATE REPLY GENERATION
# ─────────────────────────────────────────

def generate_template_reply(name, business_type, message):
    msg_lower = message.lower()

    if any(w in msg_lower for w in ["price", "cost", "pricing", "quote", "budget"]):
        intent = "pricing enquiry"
        body   = ("I'd be happy to walk you through our pricing options. "
                  "Could we schedule a quick 15-minute call so I can understand "
                  "your specific needs and give you an accurate quote?")
    elif any(w in msg_lower for w in ["demo", "trial", "test", "try"]):
        intent = "demo request"
        body   = ("Absolutely — I'd love to show you what we can do! "
                  "I'll send over a calendar link so we can find a time that works for you.")
    elif any(w in msg_lower for w in ["support", "help", "issue", "problem", "bug", "error"]):
        intent = "support request"
        body   = ("I'm sorry to hear you're running into trouble. "
                  "Our support team will be looking into this right away and "
                  "will reach out with next steps shortly.")
    elif any(w in msg_lower for w in ["partner", "collab", "integrat", "api"]):
        intent = "partnership / integration enquiry"
        body   = ("That sounds like an exciting opportunity! "
                  "I've flagged your message with our partnerships team and "
                  "someone will be in touch within 1–2 business days.")
    else:
        intent = "general enquiry"
        body   = ("Thank you for reaching out. I've reviewed your message and "
                  "will make sure the right person gets back to you with everything you need.")

    return (
        f"Hi {name},\n\n"
        f"Thank you for your {intent} — we really appreciate you taking the time to write in.\n\n"
        f"{body}\n\n"
        f"In the meantime, feel free to reply to this email if you have any other questions.\n\n"
        f"Warm regards,\n"
        f"The LeadFlow Team"
    )


def generate_ai_reply(name, email, business_type, message):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not _anthropic_available:
        return None, "fallback"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"You are a friendly, professional sales/support representative at LeadFlow.\n"
            f"Write a concise, warm reply email body (no subject line, no HTML) to the following lead:\n\n"
            f"Name          : {name}\n"
            f"Business type : {business_type}\n"
            f"Their message : {message}\n\n"
            f"Guidelines:\n"
            f"- Address them by first name\n"
            f"- Acknowledge their specific enquiry directly\n"
            f"- Offer a clear next step (call, demo link, follow-up)\n"
            f"- Keep it under 120 words\n"
            f"- End with 'Warm regards,\\nThe LeadFlow Team'\n"
            f"- Do NOT use placeholders like [X] or [insert …]\n"
            f"- Output only the email body, nothing else"
        )

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        reply_text = msg.content[0].text.strip()
        return reply_text, "ai"
    except Exception as e:
        print(f"[AI Reply] Claude API error: {e}")
        return None, "fallback"


@app.route("/api/leads/<int:lead_id>/generate-reply", methods=["POST"])
def generate_reply(lead_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()

    if not row:
        return jsonify({"error": "Lead not found."}), 404

    lead = dict(row)
    reply, source = generate_ai_reply(
        lead["name"], lead["email"], lead["business_type"], lead["message"]
    )

    if reply is None:
        reply  = generate_template_reply(lead["name"], lead["business_type"], lead["message"])
        source = "template"

    return jsonify({
        "reply":  reply,
        "source": source,
        "lead":   {k: lead[k] for k in ("name", "email", "business_type")}
    }), 200


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("LeadFlow running → http://localhost:5000")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))