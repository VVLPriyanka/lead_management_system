LeadFlow — Lead Management System

A full-stack web application to collect, track, and respond to incoming business leads — with an AI-powered reply generator built using AI.

---

Features

- **Lead Submission Form** — Customers submit their name, email, phone, business type, and message
- **Input Validation** — Both client-side (JavaScript) and server-side (Python) validation
- **Admin Dashboard** — View, search, filter, and manage all incoming leads
- **Status Tracking** — Track leads through New → Contacted → Closed pipeline
- **AI Reply Generator** — Generate personalised email replies using Claude AI with one click
- **Smart Fallback** — Template-based replies when no API key is configured
- **Auto Email Reply** — Sends an automatic email to the lead via Gmail SMTP
- **Auto Refresh** — Dashboard refreshes every 30 seconds automatically
- **Delete Leads** — Remove leads directly from the dashboard

---

Tech Stack

| Layer | Technology |

| Backend | Python, Flask |
| Database | SQLite |
| Frontend | HTML, CSS, Vanilla JavaScript |
| AI Integration | Anthropic Claude API |
| Email | Gmail SMTP |
| Environment | python-dotenv |

---

Database Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key (auto increment) |
| `name` | TEXT | Lead's full name |
| `email` | TEXT | Email address |
| `phone` | TEXT | Phone number |
| `business_type` | TEXT | Type of business (SaaS, Retail, etc.) |
| `message` | TEXT | Their enquiry message |
| `status` | TEXT | New / Contacted / Closed |
| `created_at` | TEXT | Submission timestamp |

---

API Endpoints

| Method | Endpoint | Description |

| `POST` | `/api/leads` | Submit a new lead |
| `GET` | `/api/leads` | Fetch all leads (with search & filter) |
| `PATCH` | `/api/leads/<id>/status` | Update lead status |
| `DELETE` | `/api/leads/<id>` | Delete a lead |
| `GET` | `/api/stats` | Get lead counts by status |
| `POST` | `/api/leads/<id>/generate-reply` | Generate AI reply for a lead |

---

Visit:
- **Lead Form** → http://localhost:5000
- **Admin Dashboard** → http://localhost:5000/dashboard

---

## 🤖 AI Reply Feature

The **✨ AI Reply** button on the dashboard generates a personalised email reply for each lead using **Claude AI (claude-sonnet-4-20250514)**:

- Reads the lead's name, business type, and message
- Generates a professional, concise reply with a clear next step
- Admin can **edit, regenerate, or copy** the reply
- Falls back to a smart **template-based reply** if no API key is set

To enable AI replies, set `ANTHROPIC_API_KEY` in your `.env` file.  
Get your key at: https://console.anthropic.com

---

Security

- Parameterised SQL queries to prevent SQL injection
- Server-side and client-side input validation
- API keys stored in environment variables — never hardcoded
- `.env` excluded from version control via `.gitignore`


Project Structure

lead_management_system/
├── app.py                  # Flask backend & API routes
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .gitignore
└── templates/
    ├── index.html          # Lead submission form
    └── dashboard.html      # Admin dashboard


Author

**VVL Priyanka**  
GitHub: [@VVLPriyanka](https://github.com/VVLPriyanka)
