# 🤖 AI Resume Generator

> **Ek complete resume building platform — AI-powered, multi-template, production-ready.**  
> Built with Flask, WeasyPrint, and multi-provider AI support (Groq / OpenAI / Gemini).

---

## 🚀 Live Features at a Glance

| Feature | Description |
|---|---|
| 🔐 Auth System | Email OTP + Google OAuth — dual session management |
| 📄 Resume Builder | Full-form builder with skills tags, photo upload, AI autofill |
| 🎨 9 Templates | Live preview, template switch, inline editing |
| 🤖 AI Integration | Auto-generate summary, project desc, experience bullets |
| 📥 Resume Import | Upload PDF/DOCX/TXT → AI parses & auto-fills the form |
| 📊 Admin Panel | Users, analytics, feedback, PDF manager, system settings |
| 📤 PDF Export | WeasyPrint-powered HTML → PDF with custom styling |

---

## 🛠️ Tech Stack

**Backend**
- Python + Flask
- SQLAlchemy ORM (SQLite default, swappable)
- Authlib — Google OAuth
- SMTP — Email OTP flows
- WeasyPrint — HTML → PDF generation

**Frontend**
- Jinja2 Templates + Bootstrap 5
- Vanilla JS — OTP boxes, skill tags, eye toggle
- Chart.js — Admin analytics charts

**AI Providers** *(pick one, configure via `.env`)*
- [Groq](https://groq.com) — ultra-fast inference
- [OpenAI](https://openai.com)
- [Google Gemini](https://ai.google.dev)

---

## ✨ Feature Deep Dive

### 🔐 Authentication
Three login paths, one clean UX:
- **Email signup** → OTP verification → set password
- **Email login** → password OR OTP (for Google-linked accounts)
- **Google OAuth** → instant login, optional password setup after

### 📄 Resume Builder
- Required-field validation with visual markers
- Skills as interactive tags with "Remove All" shortcut
- Photo upload (PNG/JPG/JPEG/WEBP, max 1MB)
- Project descriptions: type manually OR let AI generate them
- Save draft + come back anytime

### 🤖 AI Superpowers
Three AI endpoints, all ATS-optimized:

```
POST /api/generate-summary     → Professional ATS summary (3-4 lines)
POST /api/generate-project     → 2 bullet project description
POST /api/generate-experience  → 2 bullet work experience points
```

All prompts are carefully engineered — no markdown, no filler, recruiter-ready output.

### 📥 Smart Resume Import
Upload your existing resume → AI reads it → form gets auto-filled.  
Supports PDF, DOCX, TXT. Falls back to regex parsing if AI fails.

### 🎨 9 Resume Templates
- Live preview in browser
- Switch templates without losing data
- Inline edit mode
- One-click PDF export

### 📊 Admin Panel
Full admin suite at `/admin`:
- Dashboard stats overview
- User management (view, ban, unban, delete)
- Resume activity tracking
- Feedback with rating filter
- Analytics charts (daily users, resumes, rating distribution)
- Template usage stats
- PDF file manager
- System settings (maintenance mode, SMTP config)
- Admin activity audit logs

---

## 📁 Project Structure

```
Ai-resume-generator/
├── app.py                    # Core: models, routes, business logic
├── ai_utils.py               # AI provider router + all prompts
├── resumegenerate.py         # WeasyPrint PDF wrapper
├── requirements.txt
├── .env.example              # All config variables documented
├── AI_SETUP.md               # Detailed AI provider setup guide
├── QUICK_START.md            # Quick local setup (5 minutes)
│
├── templates/
│   ├── home.html             # Landing page
│   ├── resume.html           # Main builder form
│   ├── resume_preview.html   # Preview + export
│   ├── admin/                # Full admin UI
│   └── resume_templates/     # template_1.html → template_9.html
│
├── static/
│   ├── css/style.css         # Custom styles + OTP boxes
│   └── js/app.js             # Shared JS behaviors
│
├── resumes/                  # Generated PDFs (auto-created)
└── uploaded_photos/          # Profile photos (auto-created)
```

---

## ⚙️ Setup & Installation

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/Ai-resume-generator.git
cd Ai-resume-generator
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env with your keys (see below)
```

### 5. Run the app
```bash
python app.py
```
Visit `http://localhost:5000` 🎉

---

## 🔑 Environment Variables

```env
# Flask
SECRET_KEY=your-secret-key-here
FLASK_DEBUG=True

# Database (SQLite default)
SQLALCHEMY_DATABASE_URI=sqlite:///users.db

# Email (SMTP for OTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your@gmail.com

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# AI Provider — pick ONE
AI_PROVIDER=groq                  # groq | openai | gemini
GROQ_API_KEY=your-groq-key
# OPENAI_API_KEY=your-openai-key
# GOOGLE_API_KEY=your-gemini-key

# Admin
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=strongpassword
```

---

## 🗃️ Database Models

| Model | Purpose |
|---|---|
| `User` | Auth, profile, saved resume JSON, ban controls |
| `PendingSignup` | OTP + expiry for email verification |
| `PendingLogin` | OTP + expiry for Google-account login |
| `PendingPasswordReset` | OTP + expiry for forgot-password |
| `Feedback` | User ratings + comments |
| `Admin` | Separate admin credentials |
| `AdminSetting` | Key-value settings from admin UI |
| `AdminLog` | Audit trail of admin actions |

---

## 🤖 AI Provider Comparison

| Provider | Speed | Free Tier | Best For |
|---|---|---|---|
| **Groq** | ⚡ Fastest | ✅ Yes | Development & production |
| **OpenAI** | Medium | ❌ Paid | High accuracy |
| **Gemini** | Fast | ✅ Yes | Multimodal tasks |

> Recommended: Start with **Groq** (free, fast, no credit card needed).  
> See `AI_SETUP.md` for detailed provider configuration.

---

## 📸 Screenshots

> *(Add your own screenshots here)*
> - Home page
> - Resume builder form
> - Template preview (Template 1–9)
> - Admin dashboard
> - Generated PDF sample

---

## 🔒 Security Notes

- Passwords hashed with Werkzeug's `generate_password_hash`
- OTPs expire after a set time window
- Admin and user sessions are completely separate
- File uploads validated by extension + size
- SMTP credentials stored only in `.env` (never hardcoded)

---

## 🤝 Contributing

PRs are welcome! For major changes, open an issue first to discuss.

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source. Add your preferred license here.

---

## 👨‍💻 Author

Built with ❤️ using Flask + AI  
*Questions? Open an issue or reach out.*

---

> **⭐ Agar project useful laga toh star karna mat bhulio!**
