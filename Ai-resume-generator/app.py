from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from resumegenerate import generate_resume_pdf
from ai_utils import (
    generate_bullet_points,
    optimize_resume_content,
    extract_skills,
    generate_profile_summary,
    improve_job_description,
    summarize_text,
    generate_ats_resume_summary,
    generate_ats_project_bullets,
    generate_ats_experience_bullets,
    organize_technical_skills,
    parse_resume_form_state,
)
from sqlalchemy import func, inspect, text
import os
import base64
import re
import io
from datetime import datetime, timedelta
import random
import smtplib
import ssl
import json
from email.mime.text import MIMEText
from pathlib import Path
from functools import wraps

def load_local_env(env_path='.env'):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_local_env()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change-this-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = os.getenv('OAUTHLIB_INSECURE_TRANSPORT', '1')

db = SQLAlchemy(app)


def clean_text(value):
    cleaned = (value or '').strip()
    return '' if cleaned.lower() in {'null', 'undefined', 'none'} else cleaned


def clean_bullet_line(value):
    text = (value or '').replace('\u2022', '•')
    text = text.strip()
    if not text:
        return ''
    prefixes = ('•', '-', '*', '·', '–', '—')
    changed = True
    while changed and text:
        changed = False
        stripped = text.lstrip()
        for prefix in prefixes:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix):].lstrip()
                changed = True
        text = stripped
    return text.strip()


def clean_multiline_bullets(value):
    raw = (value or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = raw.split('\n')
    cleaned_lines = []
    for line in lines:
        if not (line or '').strip():
            continue
        if (line.lstrip()[:1] in {'•', '-', '*', '·'}):
            cleaned = clean_bullet_line(line)
            if cleaned:
                cleaned_lines.append(cleaned)
            continue
        cleaned_lines.append(line.strip())
    return "\n".join(cleaned_lines).strip()


app.jinja_env.filters['clean_bullet'] = clean_bullet_line
app.jinja_env.filters['clean_multiline_bullets'] = clean_multiline_bullets


def get_template_customizations(selected_template, source):
    template_name = normalize_template_name(selected_template)
    if template_name not in {str(i) for i in range(1, 10)}:
        template_name = '1'

    prefix = f"tpl{template_name}_"

    defaults_by_template = {
        '1': {
            'font_size': 13.0,
            'heading_color': '#0f3a57',
            'text_color': '#1f2937',
            'section_spacing': 24.0,
            'line_height': 1.65,
            'page_padding': 18.0,
            'left_padding': 18.0,
            'right_padding': 18.0,
            'heading_size': 15.0,
            'header_background': '#ffffff',
            'body_background': '#ffffff',
            'photo_size': 0.0,
            'photo_border': 0.0,
            'photo_radius': 0.0,
        },
        '2': {
            'font_size': 13.0,
            'heading_color': '#2a5ba5',
            'text_color': '#1f2937',
            'section_spacing': 20.0,
            'line_height': 1.65,
            'page_padding': 18.0,
            'left_padding': 18.0,
            'right_padding': 18.0,
            'heading_size': 15.0,
            'header_background': '#eef5ff',
            'body_background': '#ffffff',
            'photo_size': 0.0,
            'photo_border': 0.0,
            'photo_radius': 0.0,
        },
        '3': {
            'font_size': 13.0,
            'heading_color': '#334155',
            'text_color': '#1f2937',
            'section_spacing': 18.0,
            'line_height': 1.65,
            'page_padding': 16.0,
            'left_padding': 16.0,
            'right_padding': 16.0,
            'heading_size': 15.0,
            'header_background': '#ffffff',
            'body_background': '#ffffff',
            'photo_size': 0.0,
            'photo_border': 0.0,
            'photo_radius': 0.0,
        },
        '4': {
            'font_size': 13.2,
            'heading_color': '#163b5c',
            'text_color': '#12212f',
            'section_spacing': 14.0,
            'line_height': 1.5,
            'page_padding': 28.0,
            'left_padding': 30.0,
            'right_padding': 30.0,
            'heading_size': 15.0,
            'header_background': '#ffffff',
            'body_background': '#ffffff',
            'photo_size': 86.0,
            'photo_border': 2.0,
            'photo_radius': 10.0,
        },
        '5': {
            'font_size': 13.5,
            'heading_color': '#111111',
            'text_color': '#151515',
            'section_spacing': 14.0,
            'line_height': 1.45,
            'page_padding': 26.0,
            'left_padding': 30.0,
            'right_padding': 30.0,
            'heading_size': 16.0,
            'header_background': '#ffffff',
            'body_background': '#ffffff',
            'photo_size': 0.0,
            'photo_border': 0.0,
            'photo_radius': 0.0,
        },
        '6': {
            'font_size': 13.0,
            'heading_color': '#0f3a57',
            'text_color': '#1f2937',
            'section_spacing': 24.0,
            'line_height': 1.65,
            'page_padding': 18.0,
            'left_padding': 18.0,
            'right_padding': 18.0,
            'heading_size': 15.0,
            'header_background': '#eef5fb',
            'body_background': '#ffffff',
            'photo_size': 0.0,
            'photo_border': 0.0,
            'photo_radius': 0.0,
        },
        '7': {
            'font_size': 13.0,
            'heading_color': '#111827',
            'text_color': '#374151',
            'section_spacing': 18.0,
            'line_height': 1.38,
            'page_padding': 18.0,
            'left_padding': 16.0,
            'right_padding': 16.0,
            'heading_size': 15.0,
            'header_background': '#ffffff',
            'body_background': '#ffffff',
            'photo_size': 0.0,
            'photo_border': 0.0,
            'photo_radius': 0.0,
        },
        '8': {
            'font_size': 13.0,
            'heading_color': '#1f2937',
            'text_color': '#1f2937',
            'section_spacing': 18.0,
            'line_height': 1.5,
            'page_padding': 24.0,
            'left_padding': 30.0,
            'right_padding': 30.0,
            'heading_size': 15.0,
            'header_background': '#efefef',
            'body_background': '#efefef',
            'photo_size': 118.0,
            'photo_border': 0.0,
            'photo_radius': 59.0,
        },
        '9': {
            'font_size': 13.0,
            'heading_color': '#1F4E79',
            'text_color': '#111827',
            'section_spacing': 16.0,
            'line_height': 1.45,
            'page_padding': 22.0,
            'left_padding': 18.0,
            'right_padding': 18.0,
            'heading_size': 15.0,
            'header_background': '#ffffff',
            'body_background': '#ffffff',
            'photo_size': 86.0,
            'photo_border': 4.0,
            'photo_radius': 50.0,
        },
    }
    defaults = defaults_by_template.get(template_name, defaults_by_template['1'])

    def get_number(name, default, minimum, maximum):
        raw_value = (source.get(f'{prefix}{name}', '') or '').strip() if source else ''
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def get_color(name, default):
        value = (source.get(f'{prefix}{name}', '') or '').strip() if source else ''
        if len(value) == 7 and value.startswith('#'):
            return value
        return default

    return {
        'font_size': get_number('font_size', defaults['font_size'], 11.0, 18.0),
        'heading_color': get_color('heading_color', defaults['heading_color']),
        'text_color': get_color('text_color', defaults['text_color']),
        'section_spacing': get_number('section_spacing', defaults['section_spacing'], 14.0, 40.0),
        'line_height': get_number('line_height', defaults['line_height'], 1.3, 2.1),
        'page_padding': get_number('page_padding', defaults['page_padding'], 12.0, 32.0),
        'left_padding': get_number('left_padding', defaults['left_padding'], 8.0, 40.0),
        'right_padding': get_number('right_padding', defaults['right_padding'], 8.0, 40.0),
        'heading_size': get_number('heading_size', defaults['heading_size'], 12.0, 22.0),
        'header_background': get_color('header_background', defaults['header_background']),
        'body_background': get_color('body_background', defaults['body_background']),
        'photo_size': get_number('photo_size', defaults['photo_size'], 0.0, 180.0),
        'photo_border': get_number('photo_border', defaults['photo_border'], 0.0, 10.0),
        'photo_radius': get_number('photo_radius', defaults['photo_radius'], 0.0, 90.0),
    }

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200))  # nullable for Google users
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    banned_at = db.Column(db.DateTime)
    ban_reason = db.Column(db.String(255))
    profile_name = db.Column(db.String(200))
    profile_summary = db.Column(db.Text)
    profile_photo = db.Column(db.String(255))
    saved_resume_data = db.Column(db.Text)
    saved_resume_updated_at = db.Column(db.DateTime)
    has_downloaded_resume = db.Column(db.Boolean, default=False)
    last_resume_downloaded_at = db.Column(db.DateTime)
    last_resume_download_name = db.Column(db.String(255))

class PendingSignup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    verification_code = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class PendingLogin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    verification_code = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    remember_me = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class PendingPasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    verification_code = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)


class AdminSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AdminLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_email = db.Column(db.String(100), nullable=False)
    action = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TemplateUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_name = db.Column(db.String(10), unique=True, nullable=False)
    downloads = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

with app.app_context():
    db.create_all()

def migrate_user_table():
    inspector = inspect(db.engine)
    if 'user' not in inspector.get_table_names():
        return

    columns = {col['name'] for col in inspector.get_columns('user')}
    if 'is_verified' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN is_verified BOOLEAN DEFAULT 0'))
        db.session.execute(text('UPDATE "user" SET is_verified = 0 WHERE is_verified IS NULL'))
        db.session.commit()
    if 'verification_code' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN verification_code VARCHAR(6)'))
        db.session.commit()
    if 'created_at' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN created_at DATETIME'))
        db.session.execute(text('UPDATE "user" SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL'))
        db.session.commit()
    if 'is_banned' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN is_banned BOOLEAN DEFAULT 0'))
        db.session.execute(text('UPDATE "user" SET is_banned = 0 WHERE is_banned IS NULL'))
        db.session.commit()
    if 'banned_at' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN banned_at DATETIME'))
        db.session.commit()
    if 'ban_reason' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN ban_reason VARCHAR(255)'))
        db.session.commit()
    if 'profile_name' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN profile_name VARCHAR(200)'))
        db.session.commit()
    if 'profile_summary' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN profile_summary TEXT'))
        db.session.commit()
    if 'profile_photo' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN profile_photo VARCHAR(255)'))
        db.session.commit()
    if 'saved_resume_data' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN saved_resume_data TEXT'))
        db.session.commit()
    if 'saved_resume_updated_at' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN saved_resume_updated_at DATETIME'))
        db.session.commit()
    if 'has_downloaded_resume' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN has_downloaded_resume BOOLEAN DEFAULT 0'))
        db.session.execute(text('UPDATE "user" SET has_downloaded_resume = 0 WHERE has_downloaded_resume IS NULL'))
        db.session.commit()
    if 'last_resume_downloaded_at' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN last_resume_downloaded_at DATETIME'))
        db.session.commit()
    if 'last_resume_download_name' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN last_resume_download_name VARCHAR(255)'))
        db.session.commit()


def ensure_default_admin():
    default_email = (os.getenv('ADMIN_EMAIL') or '').strip().lower()
    default_password = (os.getenv('ADMIN_PASSWORD') or '').strip()
    if not default_email or not default_password:
        return
    existing = Admin.query.filter(func.lower(Admin.email) == default_email).first()
    if existing:
        return
    admin = Admin(email=default_email, password_hash=generate_password_hash(default_password), is_active=True)
    db.session.add(admin)
    db.session.commit()

# Google OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

def get_stats():
    total_users = User.query.count()
    resumes_dir = get_resumes_dir()
    resumes_generated = 0
    if os.path.isdir(resumes_dir):
        resumes_generated = sum(
            1 for filename in os.listdir(resumes_dir)
            if os.path.isfile(os.path.join(resumes_dir, filename))
        )

    feedback_count = Feedback.query.count()
    ratings = [entry.rating for entry in Feedback.query.all()]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        satisfaction = int(round((avg_rating / 5) * 100))
    else:
        satisfaction = 0
    templates = [str(i) for i in range(1, 10)]

    download_counts = {t: 0 for t in templates}
    for row in TemplateUsage.query.all():
        template_value = normalize_template_name(getattr(row, 'template_name', '1'))
        download_counts[template_value] = int(getattr(row, 'downloads', 0) or 0)

    # Keep this around for other views (and as a fallback signal), but "best template"
    # on the admin dashboard is defined as the highest download count.
    saved_counts = {t: 0 for t in templates}
    for u in User.query.filter(User.saved_resume_data.isnot(None)).all():
        raw = (u.saved_resume_data or '').strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        template_value = normalize_template_name(parsed.get('selected_template'))
        saved_counts[template_value] += 1

    best_template = max(templates, key=lambda t: (download_counts.get(t, 0), -int(t)))
    if download_counts.get(best_template, 0) == 0:
        # If nothing has been downloaded yet, fall back to the most-saved template.
        best_template = max(templates, key=lambda t: (saved_counts.get(t, 0), -int(t)))

    best_template_downloads = int(download_counts.get(best_template, 0) or 0)


    return {
        'active_users': total_users,
        'total_customers': resumes_generated,
        'resumes_generated': resumes_generated,
        'satisfaction': satisfaction,
        'feedback_count': feedback_count,
        'best_template': best_template,
        'best_template_downloads': best_template_downloads,
    }

def normalize_email(email):
    return (email or '').strip().lower()


def get_resumes_dir():
    preferred = os.path.join(app.root_path, 'resumes')
    alt = os.path.join(os.getcwd(), 'resumes')
    if os.path.isdir(preferred) or preferred == alt:
        return preferred
    if os.path.isdir(alt):
        return alt
    return preferred


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        admin_session = session.get('admin') or {}
        admin_email = (admin_session.get('email') or '').strip().lower()
        if not admin_email:
            return redirect(url_for('admin_login', next=request.path))
        admin = Admin.query.filter(func.lower(Admin.email) == admin_email).first()
        if not admin or not admin.is_active:
            session.pop('admin', None)
            return redirect(url_for('admin_login', next=request.path))
        return view_func(*args, **kwargs)

    return wrapper


def log_admin_action(admin_email, action):
    email_value = (admin_email or '').strip().lower()
    action_value = (action or '').strip()
    if not email_value or not action_value:
        return
    try:
        db.session.add(AdminLog(admin_email=email_value, action=action_value))
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_setting_value(key, default=''):
    key_value = (key or '').strip()
    if not key_value:
        return default
    entry = AdminSetting.query.filter(AdminSetting.key == key_value).first()
    return entry.value if entry else default


def is_truthy(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def apply_runtime_env_overrides():
    """
    Let admin-panel settings override env-based configuration at runtime.
    Non-empty AdminSetting values win; otherwise existing env vars remain.
    """
    mapping = {
        'AI_PROVIDER': 'ai_provider',
        'OPENAI_API_KEY': 'openai_api_key',
        'OPENAI_MODEL': 'openai_model',
        'GOOGLE_API_KEY': 'google_api_key',
        'GOOGLE_MODEL': 'google_model',
        'GROQ_API_KEY': 'groq_api_key',
        'GROQ_MODEL': 'groq_model',
    }
    for env_key, setting_key in mapping.items():
        value = (get_setting_value(setting_key, '') or '').strip()
        if value:
            os.environ[env_key] = value


def track_template_download(template_name):
    template_value = normalize_template_name(template_name)
    try:
        row = TemplateUsage.query.filter(TemplateUsage.template_name == template_value).first()
        if row:
            row.downloads = int(row.downloads or 0) + 1
            row.updated_at = datetime.utcnow()
        else:
            db.session.add(TemplateUsage(template_name=template_value, downloads=1, updated_at=datetime.utcnow()))
    except Exception:
        return


def enforce_not_banned(user):
    if not user:
        return None
    if getattr(user, 'is_banned', False):
        session.pop('user', None)
        flash('Your account has been banned. Please contact support.', 'danger')
        return redirect(url_for('login'))
    return None

def generate_verification_code():
    return f'{random.randint(0, 999999):06d}'

def send_code_email(recipient_email, subject, body):
    gmail_address = (os.getenv('GMAIL_ADDRESS') or '').strip().strip('"').strip("'")
    gmail_app_password = (os.getenv('GMAIL_APP_PASSWORD') or '').strip().strip('"').strip("'").replace(' ', '')
    smtp_host = (os.getenv('SMTP_HOST') or '').strip() or get_setting_value('smtp_host', '') or ('smtp.gmail.com' if gmail_address else '')
    smtp_port_raw = (os.getenv('SMTP_PORT') or '').strip() or get_setting_value('smtp_port', '') or '587'
    try:
        smtp_port = int(smtp_port_raw)
    except Exception:
        smtp_port = 587
    smtp_username = ((os.getenv('SMTP_USERNAME') or '').strip() or get_setting_value('smtp_username', '') or gmail_address).strip().strip('"').strip("'")
    smtp_password = ((os.getenv('SMTP_PASSWORD') or '').strip() or get_setting_value('smtp_password', '') or gmail_app_password).strip().strip('"').strip("'").replace(' ', '')
    smtp_sender = ((os.getenv('SMTP_SENDER') or '').strip() or get_setting_value('smtp_sender', '') or smtp_username or gmail_address).strip().strip('"').strip("'")
    smtp_use_tls = is_truthy((os.getenv('SMTP_USE_TLS') or '').strip() or get_setting_value('smtp_use_tls', '1'))
    smtp_use_ssl = is_truthy((os.getenv('SMTP_USE_SSL') or '').strip() or get_setting_value('smtp_use_ssl', '1' if smtp_port == 465 else '0'))

    if not smtp_host or not smtp_sender:
        return False, 'SMTP is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_SENDER.'
    if not smtp_password:
        return False, 'SMTP password is missing. Set SMTP_PASSWORD or GMAIL_APP_PASSWORD in .env.'

    message = MIMEText(body)
    message['Subject'] = subject
    message['From'] = smtp_sender
    message['To'] = recipient_email

    try:
        ssl_context = ssl.create_default_context()
        smtp_client = smtplib.SMTP_SSL if smtp_use_ssl else smtplib.SMTP

        with smtp_client(smtp_host, smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if smtp_use_tls and not smtp_use_ssl:
                smtp.starttls(context=ssl_context)
                smtp.ehlo()
            if smtp_username and smtp_password:
                smtp.login(smtp_username, smtp_password)
            smtp.sendmail(smtp_sender, [recipient_email], message.as_string())
        return True, None
    except Exception as exc:
        error_text = str(exc)
        if 'BadCredentials' in error_text or 'Username and Password not accepted' in error_text:
            return False, 'Gmail login failed. Check GMAIL_ADDRESS and 16-digit GMAIL_APP_PASSWORD in .env.'
        if 'UNEXPECTED_EOF_WHILE_READING' in error_text or 'EOF occurred in violation of protocol' in error_text:
            return False, (
                'SMTP handshake failed. Use SMTP_PORT=587 with SMTP_USE_TLS=1 and SMTP_USE_SSL=0, '
                'or SMTP_PORT=465 with SMTP_USE_SSL=1 and SMTP_USE_TLS=0.'
            )
        return False, error_text


def send_verification_email(recipient_email, verification_code):
    body = (
        'Welcome to AI Resume Generator.\n\n'
        f'Your email verification code is: {verification_code}\n\n'
        'If you did not create this account, you can ignore this message.'
    )
    return send_code_email(recipient_email, 'Verify your AI Resume Generator account', body)


def send_login_otp_email(recipient_email, verification_code):
    body = (
        'You are trying to log in to AI Resume Generator.\n\n'
        f'Your login OTP is: {verification_code}\n\n'
        'This OTP is valid for 5 minutes. If this was not you, please ignore this email.'
    )
    return send_code_email(recipient_email, 'AI Resume Generator login OTP', body)


def send_password_reset_otp_email(recipient_email, verification_code):
    body = (
        'You are trying to reset your password for AI Resume Generator.\n\n'
        f'Your password reset OTP is: {verification_code}\n\n'
        'This OTP is valid for 5 minutes. If this was not you, please ignore this email.'
    )
    return send_code_email(recipient_email, 'AI Resume Generator password reset OTP', body)


def _allowed_resume_upload(filename):
    ext = (Path(filename).suffix or '').lower().lstrip('.')
    return ext in {'pdf', 'docx', 'txt'}


def _extract_text_from_resume_upload(file_storage):
    filename = file_storage.filename or ''
    ext = (Path(filename).suffix or '').lower().lstrip('.')
    raw_bytes = file_storage.read() or b''
    if not raw_bytes:
        return None, 'Uploaded file was empty.'

    if ext == 'txt':
        try:
            return raw_bytes.decode('utf-8'), None
        except UnicodeDecodeError:
            return raw_bytes.decode('latin-1', errors='ignore'), None

    if ext == 'pdf':
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            return None, 'PDF parsing is not installed. Run: pip install pypdf'

        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages = []
            for page in reader.pages:
                try:
                    pages.append(page.extract_text() or '')
                except Exception:
                    pages.append('')
            text_value = "\n".join(pages).strip()
            return text_value, None if text_value else 'Could not extract text from this PDF.'
        except Exception as exc:
            return None, f'Could not read PDF: {exc}'

    if ext == 'docx':
        try:
            from docx import Document  # type: ignore
        except Exception:
            return None, 'DOCX parsing is not installed. Run: pip install python-docx'

        try:
            doc = Document(io.BytesIO(raw_bytes))
            text_value = "\n".join((p.text or '').strip() for p in doc.paragraphs if (p.text or '').strip()).strip()
            return text_value, None if text_value else 'Could not extract text from this DOCX.'
        except Exception as exc:
            return None, f'Could not read DOCX: {exc}'

    return None, 'Unsupported file type. Upload a PDF, DOCX, or TXT resume.'


def _guess_link_type(url):
    lower = (url or '').lower()
    if 'linkedin.com' in lower:
        return 'LinkedIn'
    if 'github.com' in lower:
        return 'GitHub'
    if 'leetcode.com' in lower:
        return 'LeetCode'
    if 'hackerrank.com' in lower:
        return 'HackerRank'
    if 'behance.net' in lower:
        return 'Behance'
    if 'dribbble.com' in lower:
        return 'Dribbble'
    return 'Portfolio'


def _parse_resume_text_to_form_state(text_value, user=None):
    raw = (text_value or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not raw:
        return {}

    # Normalize whitespace while keeping line boundaries.
    lines = []
    for line in raw.split('\n'):
        cleaned = re.sub(r'\s+', ' ', (line or '').strip())
        if cleaned:
            lines.append(cleaned)

    email_match = re.search(r'[\w\.\+\-]+@[\w\.\-]+\.\w{2,}', raw)
    email = (email_match.group(0) if email_match else '') or (getattr(user, 'email', '') or '')

    phone = ''
    phone_candidates = re.findall(r'(\+?\d[\d\-\s\(\)]{8,}\d)', raw)
    for candidate in phone_candidates:
        digits = re.sub(r'\D', '', candidate)
        if 10 <= len(digits) <= 15:
            phone = candidate.strip()
            break

    url_candidates = set()
    for match in re.findall(r'(https?://[^\s\)\]\}>,]+)', raw, flags=re.IGNORECASE):
        url_candidates.add(match.strip().rstrip('.,;'))
    for match in re.findall(r'(?:(?:www\.)?(?:linkedin\.com|github\.com|leetcode\.com|hackerrank\.com|behance\.net|dribbble\.com)/[^\s\)\]\}>,]+)', raw, flags=re.IGNORECASE):
        url = match.strip().rstrip('.,;')
        if not url.lower().startswith('http'):
            url = f'https://{url}'
        url_candidates.add(url)

    profile_link_items = [{'type': _guess_link_type(url), 'url': url} for url in sorted(url_candidates)]
    profile_links = "\n".join(item['url'] for item in profile_link_items)

    def looks_like_heading(line):
        if not line:
            return False
        lower = line.lower().strip(':').strip()
        known = {
            'summary', 'profile summary', 'objective', 'about', 'education', 'experience',
            'work experience', 'projects', 'project', 'skills', 'technical skills', 'soft skills',
            'achievements', 'certifications', 'certification', 'links',
        }
        if lower in known:
            return True
        if line.isupper() and 3 <= len(line) <= 32:
            return True
        return False

    # Guess name from first 2-4 lines.
    name_line = ''
    for candidate in lines[:6]:
        if '@' in candidate:
            continue
        if any(token in candidate.lower() for token in ['resume', 'curriculum vitae', 'cv', 'email', 'phone']):
            continue
        if len(candidate) < 3 or len(candidate) > 60:
            continue
        if re.search(r'\d', candidate):
            continue
        name_line = candidate
        break

    first_name = middle_name = last_name = ''
    if name_line:
        parts = [p for p in re.split(r'\s+', name_line.strip()) if p]
        if len(parts) == 1:
            first_name = parts[0]
        elif len(parts) == 2:
            first_name, last_name = parts
        elif len(parts) >= 3:
            first_name = parts[0]
            last_name = parts[-1]
            middle_name = " ".join(parts[1:-1])

    # Section collection
    sections = {}
    current = 'header'
    sections[current] = []
    for line in lines:
        if looks_like_heading(line):
            current = line.lower().strip(':').strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    def section_lines(*names):
        for name in names:
            bucket = sections.get(name, [])
            if bucket:
                return bucket
        return []

    summary_lines = section_lines('summary', 'profile summary', 'objective', 'about')
    summary = ''
    if summary_lines:
        summary = " ".join(summary_lines[:5]).strip()

    # Skills
    skills_lines = section_lines('skills', 'technical skills')
    skill_text = " ".join(skills_lines).replace('•', ',').replace('|', ',')
    skill_parts = [p.strip() for p in re.split(r'[,;/]', skill_text) if p.strip()]
    technical_skill_items = []
    soft_skill_items = []
    soft_keywords = {'communication', 'leadership', 'teamwork', 'collaboration', 'problem solving', 'time management'}
    for item in skill_parts:
        lowered = item.lower()
        if any(key in lowered for key in soft_keywords):
            soft_skill_items.append(item)
        else:
            technical_skill_items.append(item)
    technical_skill_items = list(dict.fromkeys(technical_skill_items))[:60]
    soft_skill_items = list(dict.fromkeys(soft_skill_items))[:30]

    # Education
    education_lines = section_lines('education')
    education_entries = []
    if education_lines:
        blocks = []
        current_block = []
        for line in education_lines:
            if looks_like_heading(line):
                break
            if line.strip():
                current_block.append(line)
        if current_block:
            blocks = re.split(r'\n{2,}', "\n".join(current_block))
        for block in blocks:
            block_lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not block_lines:
                continue
            text_block = " ".join(block_lines)
            year_match = re.search(r'(19|20)\d{2}', text_block)
            cgpa_match = re.search(r'((?:CGPA|SGPA|GPA)\s*[:\-]?\s*\d+(\.\d+)?|\d+(\.\d+)?\s*/\s*10|\d{1,3}\s*%|\d+(\.\d+)?\s*%)', text_block, flags=re.IGNORECASE)
            entry = {
                'degree': block_lines[0] if block_lines else '',
                'college': block_lines[1] if len(block_lines) > 1 else '',
                'year': year_match.group(0) if year_match else '',
                'cgpa': (cgpa_match.group(0).strip() if cgpa_match else ''),
            }
            if any(entry.values()):
                education_entries.append(entry)
    education_entries = education_entries[:6]

    # Projects
    project_lines = section_lines('projects', 'project')
    project_entries = []
    if project_lines:
        joined = "\n".join(project_lines)
        blocks = [b.strip() for b in re.split(r'\n{2,}', joined) if b.strip()]
        for block in blocks:
            block_lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not block_lines:
                continue
            title = block_lines[0]
            tech = ''
            desc_lines = block_lines[1:]
            for line in block_lines[1:]:
                if line.lower().startswith(('tech', 'stack', 'tools')):
                    tech = line.split(':', 1)[-1].strip()
                    if line in desc_lines:
                        desc_lines.remove(line)
                    break
            desc = " ".join(desc_lines).strip()
            project_entries.append({'title': title, 'tech': tech, 'desc': desc})
    project_entries = project_entries[:8]

    # Experience
    experience_lines = section_lines('experience', 'work experience')
    experience_entries = []
    if experience_lines:
        joined = "\n".join(experience_lines)
        blocks = [b.strip() for b in re.split(r'\n{2,}', joined) if b.strip()]
        for block in blocks:
            block_lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not block_lines:
                continue
            header = block_lines[0]
            role = header
            company = ''
            duration = ''
            if '|' in header:
                parts = [p.strip() for p in header.split('|') if p.strip()]
                if parts:
                    role = parts[0]
                if len(parts) > 1:
                    company = parts[1]
                if len(parts) > 2:
                    duration = parts[2]
            else:
                duration_match = re.search(r'((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}.*?(?:present|\d{4})|\d{4}\s*[-–]\s*(?:present|\d{4}))', header, flags=re.IGNORECASE)
                if duration_match:
                    duration = duration_match.group(0).strip()
                    role = header.replace(duration, '').strip(' -|')
            desc = " ".join(block_lines[1:]).replace('•', '').strip()
            experience_entries.append({'role': role, 'company': company, 'duration': duration, 'desc': desc})
    experience_entries = experience_entries[:10]

    # Achievements
    achievement_lines = section_lines('achievements')
    achievement_items = []
    if achievement_lines:
        for line in achievement_lines:
            cleaned = line.strip().lstrip('•-').strip()
            if cleaned:
                achievement_items.append(cleaned)
    achievement_items = achievement_items[:20]

    # Job title guess from first experience role if not present.
    job_title = (experience_entries[0].get('role') if experience_entries else '').strip()

    # Location guess from header line containing commas (city, country) and no url/email
    location = ''
    for candidate in lines[:10]:
        if '@' in candidate or 'http' in candidate.lower():
            continue
        if ',' in candidate and len(candidate) <= 60 and not re.search(r'\d', candidate):
            location = candidate.strip()
            break

    form_state = {
        'first_name': first_name,
        'middle_name': middle_name,
        'last_name': last_name,
        'email': email,
        'phone': phone,
        'location': location,
        'job_title': job_title,
        'summary': summary,
        'profile_links': profile_links,
        'profile_link_items': profile_link_items,
        'education_entries': education_entries,
        'project_entries': project_entries,
        'experience_entries': experience_entries,
        'achievement_items': achievement_items,
        'technical_skills': ", ".join(technical_skill_items),
        'technical_skill_items': technical_skill_items,
        'soft_skills': ", ".join(soft_skill_items),
        'soft_skill_items': soft_skill_items,
    }

    return {k: v for k, v in form_state.items() if v}

def find_users_by_email(email):
    normalized = normalize_email(email)
    return User.query.filter(func.lower(User.email) == normalized).order_by(User.id.asc()).all()

def get_primary_user(email):
    matched_users = find_users_by_email(email)
    if not matched_users:
        return None
    password_user = next((u for u in matched_users if u.password), None)
    return password_user or matched_users[0]

def deduplicate_users():
    users = User.query.order_by(User.id.asc()).all()
    by_email = {}
    duplicates = []

    for user in users:
        normalized_email = normalize_email(user.email)
        user.email = normalized_email
        if normalized_email not in by_email:
            by_email[normalized_email] = user
            continue

        existing = by_email[normalized_email]
        if existing.password and not user.password:
            duplicates.append(user)
        elif user.password and not existing.password:
            duplicates.append(existing)
            by_email[normalized_email] = user
        else:
            duplicates.append(user)

    for dup in duplicates:
        db.session.delete(dup)

    db.session.commit()

with app.app_context():
    migrate_user_table()
    deduplicate_users()
    ensure_default_admin()

def split_skills(raw_value):
    return [item.strip() for item in (raw_value or '').split(',') if item.strip()]


def parse_profile_links_for_form(raw_links):
    items = []
    for item in parse_profile_links(raw_links):
        items.append({
            'type': item.get('label', '').strip() or 'Portfolio',
            'url': item.get('url', '').strip(),
        })
    return items


def build_resume_form_state(form_data):
    profile_links = (form_data.get('profile_links', '') or '').strip()

    education_degrees = form_data.getlist('degree[]')
    education_colleges = form_data.getlist('college[]')
    education_years = form_data.getlist('year[]')
    education_score_types = form_data.getlist('score_type[]')
    education_score_values = form_data.getlist('score_value[]')
    education_scores_legacy = form_data.getlist('cgpa[]')
    if not any([education_degrees, education_colleges, education_years, education_score_types, education_score_values, education_scores_legacy]):
        education_degrees = [form_data.get('degree', '')]
        education_colleges = [form_data.get('college', '')]
        education_years = [form_data.get('year', '')]
        education_score_types = [form_data.get('score_type', '')]
        education_score_values = [form_data.get('score_value', '')]
        education_scores_legacy = [form_data.get('cgpa', '')]

    education_entries = []
    for i in range(
        max(
            len(education_degrees),
            len(education_colleges),
            len(education_years),
            len(education_score_types),
            len(education_score_values),
            len(education_scores_legacy),
        )
    ):
        degree = (education_degrees[i] if i < len(education_degrees) else '').strip()
        college = (education_colleges[i] if i < len(education_colleges) else '').strip()
        year = (education_years[i] if i < len(education_years) else '').strip()
        score_type = (education_score_types[i] if i < len(education_score_types) else '').strip() or 'CGPA'
        score_value = (education_score_values[i] if i < len(education_score_values) else '').strip()
        legacy_score = (education_scores_legacy[i] if i < len(education_scores_legacy) else '').strip()

        cgpa = ''
        if score_value:
            if score_type.lower() == 'percentage':
                cgpa = score_value if score_value.endswith('%') else f'{score_value}%'
            else:
                cgpa = f'{score_value} {score_type.upper()}'
        elif legacy_score:
            cgpa = legacy_score
        if not (degree or college or year or cgpa):
            continue
        education_entries.append({'degree': degree, 'college': college, 'year': year, 'cgpa': cgpa})

    project_titles = form_data.getlist('project_title[]')
    project_techs = form_data.getlist('project_tech[]')
    project_descs = form_data.getlist('project_desc[]')
    project_entries = []
    for i in range(max(len(project_titles), len(project_techs), len(project_descs))):
        title = (project_titles[i] if i < len(project_titles) else '').strip()
        tech = (project_techs[i] if i < len(project_techs) else '').strip()
        desc = (project_descs[i] if i < len(project_descs) else '').strip()
        if not (title or tech or desc):
            continue
        project_entries.append({'title': title, 'tech': tech, 'desc': desc})

    experience_roles = form_data.getlist('role[]')
    experience_companies = form_data.getlist('company[]')
    experience_durations = form_data.getlist('duration[]')
    experience_descs = form_data.getlist('experience_desc[]')
    experience_entries = []
    for i in range(max(len(experience_roles), len(experience_companies), len(experience_durations), len(experience_descs))):
        role = (experience_roles[i] if i < len(experience_roles) else '').strip()
        company = (experience_companies[i] if i < len(experience_companies) else '').strip()
        duration = (experience_durations[i] if i < len(experience_durations) else '').strip()
        desc = (experience_descs[i] if i < len(experience_descs) else '').strip()
        if not (role or company or duration or desc):
            continue
        experience_entries.append({'role': role, 'company': company, 'duration': duration, 'desc': desc})

    achievement_items = [item.strip() for item in form_data.getlist('achievement_item[]') if item.strip()]
    if not achievement_items:
        achievement_items = [item.strip().lstrip('- ').strip() for item in (form_data.get('achievements', '') or '').splitlines() if item.strip()]

    return {
        'first_name': (form_data.get('first_name', '') or '').strip(),
        'middle_name': (form_data.get('middle_name', '') or '').strip(),
        'last_name': (form_data.get('last_name', '') or '').strip(),
        'email': (form_data.get('email', '') or '').strip(),
        'phone': (form_data.get('phone', '') or '').strip(),
        'location': (form_data.get('location', '') or '').strip(),
        'job_title': (form_data.get('job_title', '') or '').strip(),
        'experience_value': (form_data.get('experience_value', '') or '').strip(),
        'experience_unit': (form_data.get('experience_unit', '') or 'none').strip(),
        'summary': (form_data.get('summary', '') or '').strip(),
        'profile_links': profile_links,
        'profile_link_items': parse_profile_links_for_form(profile_links),
        'education_entries': education_entries,
        'project_entries': project_entries,
        'experience_entries': experience_entries,
        'achievement_items': achievement_items,
        'technical_skills': (form_data.get('technical_skills', '') or '').strip(),
        'technical_skill_items': split_skills(form_data.get('technical_skills', '')),
        'technical_skills_grouped': (form_data.get('technical_skills_grouped', '') or '').strip(),
        'soft_skills': (form_data.get('soft_skills', '') or '').strip(),
        'soft_skill_items': split_skills(form_data.get('soft_skills', '')),
        'selected_template': normalize_template_name(form_data.get('selected_template', '1')),
    }


def default_resume_form_state(user=None):
    return {
        'first_name': '',
        'middle_name': '',
        'last_name': '',
        'email': '',
        'phone': '',
        'location': '',
        'job_title': '',
        'experience_value': '',
        'experience_unit': 'none',
        'summary': '',
        'profile_links': '',
        'profile_link_items': [],
        'education_entries': [],
        'project_entries': [],
        'experience_entries': [],
        'achievement_items': [],
        'technical_skills': '',
        'technical_skill_items': [],
        'technical_skills_grouped': '',
        'soft_skills': '',
        'soft_skill_items': [],
        'selected_template': '1',
        'photo_filename': getattr(user, 'profile_photo', None),
    }


def get_saved_resume_state(user):
    base_state = default_resume_form_state(user)
    raw_state = (user.saved_resume_data if user else None) or ''
    if not raw_state:
        return base_state
    try:
        parsed = json.loads(raw_state)
    except (TypeError, ValueError, json.JSONDecodeError):
        return base_state
    if not isinstance(parsed, dict):
        return base_state

    merged = dict(base_state)
    merged.update(parsed)
    merged.pop('canvas_mode', None)
    merged.pop('canvas_layout', None)
    merged.pop('canvas_page_count', None)
    merged['selected_template'] = normalize_template_name(merged.get('selected_template', '1'))
    merged['profile_link_items'] = merged.get('profile_link_items') or parse_profile_links_for_form(merged.get('profile_links', ''))
    merged['technical_skill_items'] = merged.get('technical_skill_items') or split_skills(merged.get('technical_skills', ''))
    merged['soft_skill_items'] = merged.get('soft_skill_items') or split_skills(merged.get('soft_skills', ''))
    merged['education_entries'] = merged.get('education_entries') or []
    merged['project_entries'] = merged.get('project_entries') or []
    merged['experience_entries'] = merged.get('experience_entries') or []
    merged['achievement_items'] = merged.get('achievement_items') or []
    merged['photo_filename'] = merged.get('photo_filename') or getattr(user, 'profile_photo', None)
    return merged


def sync_user_resume_state(user, form_state, resume_data=None, photo_filename=None):
    if not user or not form_state:
        return

    selected_photo = photo_filename or form_state.get('photo_filename') or user.profile_photo
    stored_state = get_saved_resume_state(user) or default_resume_form_state(user)
    if not isinstance(stored_state, dict):
        stored_state = default_resume_form_state(user)
    stored_state.update(dict(form_state))
    stored_state['selected_template'] = normalize_template_name(stored_state.get('selected_template', '1'))
    stored_state['photo_filename'] = selected_photo

    full_name = (resume_data or {}).get('full_name', '').strip()
    if not full_name:
        full_name = " ".join(
            part for part in [
                stored_state.get('first_name', '').strip(),
                stored_state.get('middle_name', '').strip(),
                stored_state.get('last_name', '').strip(),
            ] if part
        )

    user.profile_name = full_name or user.profile_name
    user.profile_summary = (stored_state.get('summary') or '').strip()
    user.profile_photo = selected_photo
    user.saved_resume_data = json.dumps(stored_state)
    user.saved_resume_updated_at = datetime.utcnow()
    db.session.commit()

def extract_resume_data(form_data):
    form_state = build_resume_form_state(form_data)
    first_name = clean_text(form_state['first_name'])
    middle_name = clean_text(form_state['middle_name'])
    last_name = clean_text(form_state['last_name'])
    full_name = " ".join(part for part in [first_name, middle_name, last_name] if part)
    if not full_name:
        full_name = (form_data.get('full_name', '') or '').strip()

    education_entries = form_state['education_entries']
    primary_education = education_entries[0] if education_entries else {
        'degree': '',
        'college': '',
        'year': '',
        'cgpa': '',
    }

    project_blocks = []
    for entry in form_state['project_entries']:
        title = clean_text(entry['title'])
        tech = clean_text(entry['tech'])
        desc = clean_text(entry['desc'])
        lines = []
        if title:
            lines.append(f'Project {len(project_blocks) + 1}: {title}')
        if tech:
            lines.append(f'Technologies: {tech}')
        if desc:
            lines.append(desc)
        project_blocks.append("\n".join(lines))

    experience_blocks = []
    for entry in form_state['experience_entries']:
        role = clean_text(entry['role'])
        company = clean_text(entry['company'])
        duration = clean_text(entry['duration'])
        desc = clean_text(entry['desc'])
        header = " - ".join([part for part in [role, company] if part]).strip()
        lines = []
        if header:
            lines.append(f'Experience {len(experience_blocks) + 1}: {header}')
        if duration:
            lines.append(f'Duration: {duration}')
        if desc:
            lines.append(desc)
        experience_blocks.append("\n".join(lines))

    achievement_items = form_state['achievement_items']
    achievements_text = "\n".join(f'- {item}' for item in achievement_items)
    if not achievements_text:
        achievements_text = (form_data.get('achievements', '') or '').strip()

    return {
        'full_name': full_name,
        'email': form_state['email'],
        'phone': form_state['phone'],
        'location': form_state['location'],
        'job_title': form_state['job_title'],
        'experience_value': form_state.get('experience_value', ''),
        'experience_unit': form_state.get('experience_unit', 'none'),
        'profile_links': form_state['profile_links'],
        'summary': form_state['summary'],
        'degree': primary_education['degree'],
        'college': primary_education['college'],
        'year': primary_education['year'],
        'cgpa': primary_education['cgpa'],
        'education_entries': education_entries,
        'technical_skills': form_state['technical_skills'],
        'technical_skills_grouped': form_state.get('technical_skills_grouped', ''),
        'soft_skills': form_state['soft_skills'],
        'project_title': project_blocks[0].split('\n')[0].replace('Project 1: ', '') if project_blocks else '',
        'project_tech': '',
        'project_desc': "\n\n".join(project_blocks),
        'role': '',
        'company': '',
        'duration': '',
        'experience_desc': "\n\n".join(experience_blocks),
        'achievements': achievements_text,
        'selected_template': form_state['selected_template'],
        'template_customizations': get_template_customizations(form_state['selected_template'], form_data),
        'section_orders': form_state.get('section_orders') or {},
    }


def get_uploaded_photos_dir():
    upload_dir = os.path.join(app.root_path, 'uploaded_photos')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def save_uploaded_photo(file_storage, data_url=None):
    if data_url:
        value = (data_url or '').strip()
        match = None
        if value.startswith('data:image/'):
            match = value.split(',', 1)
        if match and len(match) == 2:
            header, encoded = match[0], match[1]
            ext = 'png'
            if 'image/jpeg' in header:
                ext = 'jpg'
            elif 'image/webp' in header:
                ext = 'webp'
            elif 'image/png' in header:
                ext = 'png'
            else:
                return None

            try:
                raw = base64.b64decode(encoded)
            except Exception:
                return None

            # Size guard (max 1 MB)
            if not raw or len(raw) > 1_000_000:
                return None

            filename = f"{int(datetime.utcnow().timestamp())}-cropped.{ext}"
            with open(os.path.join(get_uploaded_photos_dir(), filename), 'wb') as photo_file:
                photo_file.write(raw)
            return filename

    if not file_storage or not file_storage.filename:
        return None

    extension = os.path.splitext(file_storage.filename)[1].lower()
    if extension not in {'.png', '.jpg', '.jpeg', '.webp'}:
        return None

    try:
        file_storage.stream.seek(0, os.SEEK_END)
        size = int(file_storage.stream.tell() or 0)
        file_storage.stream.seek(0)
    except Exception:
        size = int(getattr(file_storage, 'content_length', 0) or 0)
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
    if size and size > 1_000_000:
        return None

    filename = f"{int(datetime.utcnow().timestamp())}-{secure_filename(file_storage.filename)}"
    file_storage.save(os.path.join(get_uploaded_photos_dir(), filename))
    return filename


def parse_profile_links(raw_links):
    items = []
    for chunk in (raw_links or '').split('|'):
        entry = chunk.strip()
        if not entry:
            continue

        label = ''
        url = entry
        if ': ' in entry:
            possible_label, possible_url = entry.split(': ', 1)
            if possible_url.lower().startswith(('http://', 'https://')):
                label = possible_label.strip()
                url = possible_url.strip()

        normalized_url = url.strip()
        if not normalized_url.lower().startswith(('http://', 'https://')):
            continue

        if not label:
            lowered = normalized_url.lower()
            if 'linkedin.com' in lowered:
                label = 'LinkedIn'
            elif 'github.com' in lowered:
                label = 'GitHub'
            else:
                label = 'Portfolio'

        items.append({'label': label, 'url': normalized_url})
    return items


def get_photo_src(photo_filename, preview_mode=True):
    if not photo_filename:
        return None
    if preview_mode:
        return url_for('uploaded_photo', filename=photo_filename)
    return Path(os.path.join(get_uploaded_photos_dir(), photo_filename)).resolve().as_uri()


def attach_resume_media(resume_data, photo_filename=None, preview_mode=True):
    prepared = dict(resume_data or {})
    selected_photo = photo_filename or prepared.get('photo_filename')
    prepared['photo_filename'] = selected_photo
    prepared['profile_link_items'] = parse_profile_links(prepared.get('profile_links'))

    if not selected_photo:
        prepared['photo_src'] = None
        return prepared

    prepared['photo_src'] = get_photo_src(selected_photo, preview_mode=preview_mode)
    return prepared


def template_requires_photo(template_name):
    return normalize_template_name(template_name) in {'8', '9'}


def get_resume_download_name(resume_data, extension, template_name='1'):
    full_name = (resume_data.get('full_name', '') or '').strip()
    first_name = full_name.split()[0] if full_name else 'resume'
    safe_first_name = ''.join(ch.lower() if ch.isalnum() else '-' for ch in first_name).strip('-')
    while '--' in safe_first_name:
        safe_first_name = safe_first_name.replace('--', '-')
    if not safe_first_name:
        safe_first_name = 'resume'
    return f'{safe_first_name}resume.{extension}'


def normalize_template_name(value):
    template_name = (value or '1').strip().lower()
    legacy_map = {
        'classic': '1',
        'executive': '2',
        'compact': '3',
    }
    template_name = legacy_map.get(template_name, template_name)
    return template_name if template_name in {'1', '2', '3', '4', '5', '6', '7', '8', '9'} else '1'

@app.route('/')
def home():
    stats = get_stats()
    feedback_entries = Feedback.query.order_by(Feedback.created_at.desc()).limit(6).all()
    return render_template('home.html', stats=stats, user=session.get('user'), feedback_entries=feedback_entries)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user'):
        return redirect(url_for('home'))
    if request.method == 'POST':
        stage = (request.form.get('stage') or 'email').strip().lower()
        email = normalize_email(request.form.get('email'))
        user = get_primary_user(email)

        if stage == 'email':
            if not user:
                flash('No account found with this email. Please sign up first.', 'warning')
                return redirect(url_for('register', email=email))
            if user.is_banned:
                flash("Your account has been banned. You can't log in.", 'danger')
                return redirect(url_for('login'))

            if not user.is_verified:
                flash('Please verify your email first.', 'warning')
                return redirect(url_for('verify', email=user.email))

            if not user.password:
                flash('This account uses Google sign-in only. Please use "Sign in with Google".', 'info')
                return render_template('login.html', stage='email', prefill_email=email)

            return redirect(url_for('login', stage='password', email=email))

        if stage == 'password':
            password = request.form.get('password', '')
            if not user or not user.password:
                flash('This account uses Google sign-in only. Please use "Sign in with Google".', 'info')
                return redirect(url_for('login'))
            if user.is_banned:
                flash('Your account has been banned. Please contact support.', 'danger')
                return redirect(url_for('login'))

            if not user.is_verified:
                flash('Please verify your email first.', 'warning')
                return redirect(url_for('verify', email=user.email))

            if not check_password_hash(user.password, password):
                flash('Invalid email or password.', 'danger')
                return render_template('login.html', stage='password', prefill_email=email)

            remember_me = bool(request.form.get('remember_me'))
            session.permanent = remember_me
            session['user'] = {'email': user.email}
            flash('Login successful.', 'success')
            return redirect(url_for('home'))

    requested_stage = (request.args.get('stage') or 'email').strip().lower()
    prefill_email = normalize_email(request.args.get('email'))
    stage = 'email'
    if requested_stage == 'password' and prefill_email:
        existing = get_primary_user(prefill_email)
        if existing and existing.is_verified and existing.password:
            stage = 'password'
    return render_template('login.html', stage=stage, prefill_email=prefill_email)


@app.route('/login/verify', methods=['GET', 'POST'])
def login_verify():
    if session.get('user'):
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = normalize_email(request.form.get('email'))
        code = (request.form.get('code') or '').strip()
        pending_login = PendingLogin.query.filter(func.lower(PendingLogin.email) == email).first()

        if not pending_login:
            flash('No pending login verification was found. Please log in again.', 'warning')
            return redirect(url_for('login'))

        if datetime.utcnow() > pending_login.expires_at:
            db.session.delete(pending_login)
            db.session.commit()
            flash('Your login OTP expired. Please log in again.', 'warning')
            return redirect(url_for('login'))

        if pending_login.verification_code != code:
            flash('Invalid OTP. Please try again.', 'danger')
            return redirect(url_for('login_verify', email=email))

        user = get_primary_user(email)
        if not user or not user.is_verified:
            db.session.delete(pending_login)
            db.session.commit()
            flash('Account not found or not verified. Please log in again.', 'warning')
            return redirect(url_for('login'))
        if user.is_banned:
            db.session.delete(pending_login)
            db.session.commit()
            flash('Your account has been banned. Please contact support.', 'danger')
            return redirect(url_for('login'))

        session.permanent = bool(pending_login.remember_me)
        session['user'] = {'email': user.email}
        db.session.delete(pending_login)
        db.session.commit()
        flash('Login successful.', 'success')
        return redirect(url_for('home'))

    prefill_email = normalize_email(request.args.get('email'))
    return render_template('login_verify.html', prefill_email=prefill_email)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        stage = (request.form.get('stage') or 'email').strip().lower()
        email = normalize_email(request.form.get('email'))

        if stage == 'email':
            user = get_primary_user(email)
            if not user:
                flash('No account found with this email. Please sign up.', 'warning')
                return redirect(url_for('register', email=email))
            if user.is_banned:
                flash('Your account has been banned. Please contact support.', 'danger')
                return redirect(url_for('login'))

            verification_code = generate_verification_code()
            pending_reset = PendingPasswordReset.query.filter(func.lower(PendingPasswordReset.email) == email).first()
            if pending_reset:
                pending_reset.verification_code = verification_code
                pending_reset.expires_at = datetime.utcnow() + timedelta(minutes=5)
            else:
                pending_reset = PendingPasswordReset(
                    email=user.email,
                    verification_code=verification_code,
                    expires_at=datetime.utcnow() + timedelta(minutes=5),
                )
                db.session.add(pending_reset)
            db.session.commit()

            sent, error = send_password_reset_otp_email(user.email, verification_code)
            if not sent:
                flash(f'Could not send password reset OTP: {error}', 'danger')
                return redirect(url_for('forgot_password'))

            flash('We sent a password reset OTP to your email. It is valid for 5 minutes.', 'info')
            return redirect(url_for('forgot_password', stage='otp', email=user.email))

        if stage == 'otp':
            code = (request.form.get('code') or '').strip()
            pending_reset = PendingPasswordReset.query.filter(func.lower(PendingPasswordReset.email) == email).first()
            if not pending_reset:
                flash('No pending password reset was found. Please try again.', 'warning')
                return redirect(url_for('forgot_password'))

            if datetime.utcnow() > pending_reset.expires_at:
                db.session.delete(pending_reset)
                db.session.commit()
                flash('Your password reset OTP expired. Please try again.', 'warning')
                return redirect(url_for('forgot_password'))

            if pending_reset.verification_code != code:
                flash('Invalid OTP. Please try again.', 'danger')
                return redirect(url_for('forgot_password', stage='otp', email=email))

            session['password_reset_email'] = email
            flash('OTP verified. Please set a new password.', 'success')
            return redirect(url_for('forgot_password', stage='password', email=email))

        if stage == 'password':
            verified_email = normalize_email(session.get('password_reset_email'))
            if not verified_email or verified_email != email:
                flash('Please verify OTP first.', 'warning')
                return redirect(url_for('forgot_password'))

            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not new_password or not confirm_password:
                flash('Please fill all fields.', 'warning')
                return redirect(url_for('forgot_password', stage='password', email=email))

            if len(new_password) < 6:
                flash('Password must be at least 6 characters.', 'warning')
                return redirect(url_for('forgot_password', stage='password', email=email))

            if new_password != confirm_password:
                flash('Passwords do not match.', 'warning')
                return redirect(url_for('forgot_password', stage='password', email=email))

            user = get_primary_user(email)
            if not user:
                flash('No account found with this email. Please sign up.', 'warning')
                session.pop('password_reset_email', None)
                return redirect(url_for('register', email=email))

            user.password = generate_password_hash(new_password)
            pending_reset = PendingPasswordReset.query.filter(func.lower(PendingPasswordReset.email) == email).first()
            if pending_reset:
                db.session.delete(pending_reset)
            db.session.commit()
            session.pop('password_reset_email', None)
            flash('Password reset successful. Please login.', 'success')
            return redirect(url_for('login', email=email))

    stage = (request.args.get('stage') or 'email').strip().lower()
    if stage not in {'email', 'otp', 'password'}:
        stage = 'email'
    prefill_email = normalize_email(request.args.get('email'))
    if stage in {'otp', 'password'} and not prefill_email:
        stage = 'email'
    if stage == 'password':
        verified_email = normalize_email(session.get('password_reset_email'))
        if not verified_email or verified_email != prefill_email:
            stage = 'email'
    return render_template('forgot_password.html', stage=stage, prefill_email=prefill_email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user'):
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = normalize_email(request.form.get('email'))
        password = request.form.get('password', '')
        if not email or not password:
            flash('Please fill all fields.', 'warning')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
            return redirect(url_for('register'))
        existing_user = get_primary_user(email)
        if existing_user:
            if existing_user.is_verified:
                flash('Email already registered, please login.', 'warning')
                return redirect(url_for('login'))
            db.session.delete(existing_user)
            db.session.commit()
        hashed_password = generate_password_hash(password)
        verification_code = generate_verification_code()
        sent, error = send_verification_email(email, verification_code)
        if not sent:
            flash(f'Could not send verification email: {error}', 'danger')
            return redirect(url_for('register'))

        pending = PendingSignup.query.filter(func.lower(PendingSignup.email) == email).first()
        if pending:
            pending.password = hashed_password
            pending.verification_code = verification_code
            pending.expires_at = datetime.utcnow() + timedelta(minutes=5)
        else:
            pending = PendingSignup(
                email=email,
                password=hashed_password,
                verification_code=verification_code,
                expires_at=datetime.utcnow() + timedelta(minutes=5),
            )
            db.session.add(pending)
        db.session.commit()
        flash('Verification code sent. It will expire in 5 minutes.', 'success')
        return redirect(url_for('verify', email=email))

    prefill_email = normalize_email(request.args.get('email'))
    return render_template('register.html', prefill_email=prefill_email)

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        email = normalize_email(request.form.get('email'))
        code = (request.form.get('code') or '').strip()
        pending = PendingSignup.query.filter(func.lower(PendingSignup.email) == email).first()

        if not pending:
            flash('No pending verification found for this email. Please sign up again.', 'warning')
            return redirect(url_for('register'))

        if datetime.utcnow() > pending.expires_at:
            db.session.delete(pending)
            db.session.commit()
            flash('Verification code expired. Please sign up again.', 'warning')
            return redirect(url_for('register'))

        if code and pending.verification_code == code:
            existing_user = get_primary_user(email)
            if existing_user:
                if existing_user.is_verified:
                    db.session.delete(pending)
                    db.session.commit()
                    flash('Email already registered. Please login.', 'warning')
                    return redirect(url_for('login'))
                db.session.delete(existing_user)

            new_user = User(email=pending.email, password=pending.password, is_verified=True, verification_code=None)
            db.session.add(new_user)
            db.session.delete(pending)
            db.session.commit()
            session.permanent = False
            session['user'] = {'email': new_user.email}
            flash('Email verified successfully!', 'success')
            return redirect(url_for('home'))

        flash('Invalid email or code.', 'danger')
        return redirect(url_for('verify', email=email))

    prefill_email = normalize_email(request.args.get('email'))
    return render_template('verify.html', prefill_email=prefill_email)

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
    except Exception:
        flash('Google authorization failed. Check redirect URI and OAuth credentials.', 'danger')
        return redirect(url_for('login'))

    user_info = token.get('userinfo')
    if not user_info:
        try:
            userinfo_endpoint = google.server_metadata.get('userinfo_endpoint')
            if userinfo_endpoint:
                user_info = google.get(userinfo_endpoint).json()
        except Exception:
            user_info = None

    if not user_info or not user_info.get('email'):
        flash('Google login failed: email not returned by Google.', 'danger')
        return redirect(url_for('login'))
    # Register user if not exists
    google_email = normalize_email(user_info.get('email'))
    user = get_primary_user(google_email)
    is_new_google_user = False
    if not user:
        user = User(email=google_email, password=None, is_verified=True, verification_code=None)
        db.session.add(user)
        db.session.commit()
        is_new_google_user = True
    elif not user.is_verified:
        user.is_verified = True
        user.verification_code = None
        db.session.commit()

    session.permanent = True
    session['user'] = {'email': user.email}
    flash('Logged in with Google!', 'success')
    return redirect(url_for('home'))


@app.route('/set-password', methods=['GET', 'POST'])
def set_password():
    current_user = session.get('user')
    if not current_user:
        return redirect(url_for('login'))

    user = get_primary_user(current_user.get('email'))
    if not user:
        session.pop('user', None)
        flash('Account not found. Please login again.', 'warning')
        return redirect(url_for('login'))

    if not user.password:
        flash('This account uses Google sign-in only.', 'info')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password or not confirm_password:
            flash('Please fill all fields.', 'warning')
            return redirect(url_for('set_password'))
        if len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
            return redirect(url_for('set_password'))
        if new_password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for('set_password'))

        user.password = generate_password_hash(new_password)
        db.session.commit()
        session['user'] = {'email': user.email}
        flash('Password saved successfully. You can now log in with email too.', 'success')
        return redirect(url_for('account'))

    return render_template('set_password.html')


@app.route('/dashboard')
def dashboard():
    return redirect(url_for('home'))


@app.route('/resume')
def resume():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))
    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    saved_resume = get_saved_resume_state(user)
    profile_photo_src = get_photo_src(saved_resume.get('photo_filename'), preview_mode=True)
    return render_template(
        'resume.html',
        user=user,
        saved_resume=saved_resume,
        profile_photo_src=profile_photo_src,
        has_saved_resume=bool(user.saved_resume_data),
    )


@app.route('/resume/import', methods=['POST'])
def import_resume():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    file_storage = request.files.get('resume_file')
    if not file_storage or not (file_storage.filename or '').strip():
        flash('Please choose a resume file to upload.', 'warning')
        return redirect(url_for('resume'))

    if not _allowed_resume_upload(file_storage.filename):
        flash('Unsupported file type. Upload a PDF, DOCX, or TXT resume.', 'warning')
        return redirect(url_for('resume'))

    text_value, error = _extract_text_from_resume_upload(file_storage)
    if error:
        flash(error, 'danger')
        return redirect(url_for('resume'))

    imported_state = {}
    ai_error = None
    try:
        imported_state = parse_resume_form_state(text_value) or {}
    except Exception as exc:
        ai_error = str(exc)

    if not imported_state:
        imported_state = _parse_resume_text_to_form_state(text_value, user=user)
        if ai_error:
            flash(f'AI parsing failed ({ai_error}). Used basic parsing instead.', 'warning')
    if not imported_state:
        flash('Could not extract resume details from this file. Try a text-based PDF/DOCX.', 'warning')
        return redirect(url_for('resume'))

    stored_state = get_saved_resume_state(user) or default_resume_form_state(user)

    def merge_value(key):
        value = imported_state.get(key)
        if value is None or value == '' or value == []:
            return
        stored_state[key] = value

    for key in [
        'first_name', 'middle_name', 'last_name', 'email', 'phone', 'location', 'job_title',
        'summary', 'profile_links', 'technical_skills', 'soft_skills',
    ]:
        merge_value(key)

    for key in [
        'profile_link_items', 'education_entries', 'project_entries', 'experience_entries',
        'achievement_items', 'technical_skill_items', 'soft_skill_items',
    ]:
        merge_value(key)

    stored_state['selected_template'] = normalize_template_name(stored_state.get('selected_template', '1'))
    stored_state['profile_link_items'] = stored_state.get('profile_link_items') or parse_profile_links_for_form(stored_state.get('profile_links', ''))
    stored_state['technical_skill_items'] = stored_state.get('technical_skill_items') or split_skills(stored_state.get('technical_skills', ''))
    stored_state['soft_skill_items'] = stored_state.get('soft_skill_items') or split_skills(stored_state.get('soft_skills', ''))

    full_name = " ".join(
        part for part in [
            stored_state.get('first_name', '').strip(),
            stored_state.get('middle_name', '').strip(),
            stored_state.get('last_name', '').strip(),
        ] if part
    ).strip()
    sync_user_resume_state(
        user,
        stored_state,
        resume_data={'full_name': full_name},
        photo_filename=stored_state.get('photo_filename') or user.profile_photo,
    )
    flash('Resume imported. Please review and edit the autofilled details.', 'success')
    return redirect(url_for('resume'))


@app.route('/resume/save', methods=['POST'])
def save_resume():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    form_state = build_resume_form_state(request.form)
    resume_data = extract_resume_data(request.form)
    incoming_photo = request.files.get('photo')
    incoming_data_url = request.form.get('photo_data_url')
    photo_filename = save_uploaded_photo(incoming_photo, incoming_data_url)
    if (incoming_data_url or getattr(incoming_photo, 'filename', '')) and not photo_filename:
        flash('Photo upload failed. Max size is 1 MB. Supported: PNG, JPG, JPEG, WEBP.', 'warning')
        return redirect(url_for('resume') + '#photo-upload-section')
    photo_filename = photo_filename or user.profile_photo
    resume_data['photo_filename'] = photo_filename
    form_state['photo_filename'] = photo_filename
    session['selected_template'] = form_state['selected_template']
    session['resume_data'] = resume_data
    sync_user_resume_state(user, form_state, resume_data=resume_data, photo_filename=photo_filename)
    flash('Your details have been saved. You can continue later without re-entering them.', 'success')
    return redirect(url_for('resume'))


@app.route('/preview', methods=['GET', 'POST'])
def preview_resume():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    if request.method == 'GET':
        resume_data = session.get('resume_data')
        if not resume_data:
            flash('Please open a preview from the form first.', 'warning')
            return redirect(url_for('resume'))
        photo_filename = (resume_data or {}).get('photo_filename') or user.profile_photo
        return render_template('resume_preview.html', user=user, data=attach_resume_media(resume_data, photo_filename=photo_filename))

    form_state = build_resume_form_state(request.form)
    resume_data = extract_resume_data(request.form)
    incoming_photo = request.files.get('photo')
    incoming_data_url = request.form.get('photo_data_url')
    photo_filename = save_uploaded_photo(incoming_photo, incoming_data_url)
    if (incoming_data_url or getattr(incoming_photo, 'filename', '')) and not photo_filename:
        flash('Photo upload failed. Max size is 1 MB. Supported: PNG, JPG, JPEG, WEBP.', 'warning')
        return redirect(url_for('resume') + '#photo-upload-section')
    if not photo_filename:
        photo_filename = (session.get('resume_data') or {}).get('photo_filename') or user.profile_photo
    template_name = normalize_template_name(request.form.get('selected_template'))
    if template_requires_photo(template_name) and not photo_filename:
        flash('Please choose photo first.', 'warning')
        return redirect(url_for('resume'))
    resume_data['selected_template'] = template_name
    resume_data['photo_filename'] = photo_filename
    saved_state = get_saved_resume_state(user) or {}
    if not (resume_data.get('section_orders') or {}):
        resume_data['section_orders'] = saved_state.get('section_orders') or {}
    form_state['selected_template'] = template_name
    form_state['photo_filename'] = photo_filename
    session['selected_template'] = template_name
    session['resume_data'] = resume_data
    sync_user_resume_state(user, form_state, resume_data=resume_data, photo_filename=photo_filename)
    return render_template('resume_preview.html', user=user, data=attach_resume_media(resume_data, photo_filename=photo_filename))


@app.route('/preview/photo', methods=['POST'])
def preview_update_photo():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    incoming_photo = request.files.get('photo')
    if not incoming_photo or not getattr(incoming_photo, 'filename', ''):
        flash('Please choose a photo to upload.', 'warning')
        return redirect(url_for('preview_resume'))

    photo_filename = save_uploaded_photo(incoming_photo, None)
    if not photo_filename:
        flash('Photo upload failed. Max size is 1 MB. Supported: PNG, JPG, JPEG, WEBP.', 'warning')
        return redirect(url_for('preview_resume'))

    resume_data = session.get('resume_data') or {}
    resume_data['photo_filename'] = photo_filename
    session['resume_data'] = resume_data

    stored_state = get_saved_resume_state(user) or default_resume_form_state(user)
    stored_state['photo_filename'] = photo_filename
    full_name = " ".join(
        part for part in [
            stored_state.get('first_name', '').strip(),
            stored_state.get('middle_name', '').strip(),
            stored_state.get('last_name', '').strip(),
        ] if part
    ).strip()
    sync_user_resume_state(user, stored_state, resume_data={'full_name': full_name}, photo_filename=photo_filename)
    flash('Photo updated.', 'success')
    return redirect(url_for('preview_resume'))


def render_resume_pdf_html(resume_data):
    return render_template('resume_pdf.html', data=attach_resume_media(resume_data, preview_mode=False))


@app.route('/api/preview/render-template/<template_id>', methods=['POST'])
def api_render_template_thumb(template_id):
    session_user = session.get('user')
    if not session_user:
        return ('Unauthorized', 401)

    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return ('Unauthorized', 401)

    template_name = normalize_template_name(template_id)
    resume_data = extract_resume_data(request.form)
    resume_data['selected_template'] = template_name
    resume_data['template_customizations'] = get_template_customizations(template_name, request.form)

    in_memory_photo_src = None
    photo_data_url = (request.form.get('photo_data_url') or '').strip()
    if photo_data_url.startswith('data:image/'):
        # Approx size check for thumbnails (max 1 MB decoded)
        try:
            encoded = photo_data_url.split(',', 1)[1]
            raw = base64.b64decode(encoded)
            if raw and len(raw) <= 1_000_000:
                in_memory_photo_src = photo_data_url
        except Exception:
            in_memory_photo_src = None
    else:
        photo_upload = request.files.get('photo')
        if photo_upload and getattr(photo_upload, 'filename', ''):
            raw = photo_upload.read()
            try:
                photo_upload.stream.seek(0)
            except Exception:
                pass
            if raw and len(raw) <= 1_000_000:
                mime = (getattr(photo_upload, 'mimetype', None) or '').strip() or 'image/png'
                if not mime.startswith('image/'):
                    mime = 'image/png'
                in_memory_photo_src = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    photo_filename = None
    if not in_memory_photo_src:
        photo_filename = (session.get('resume_data') or {}).get('photo_filename') or user.profile_photo
        resume_data['photo_filename'] = photo_filename

    prepared = attach_resume_media(resume_data, photo_filename=photo_filename, preview_mode=True)
    if in_memory_photo_src:
        prepared['photo_filename'] = None
        prepared['photo_src'] = in_memory_photo_src

    html = render_template('resume_template_embed.html', data=prepared)
    return (html, 200, {'Content-Type': 'text/html; charset=utf-8'})


@app.route('/uploaded-photos/<path:filename>')
def uploaded_photo(filename):
    return send_from_directory(get_uploaded_photos_dir(), filename)


@app.route('/export/<file_format>', methods=['GET', 'POST'])
def export_resume(file_format):
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    file_format = (file_format or '').lower()
    if file_format != 'pdf':
        flash('Unsupported export format.', 'warning')
        return redirect(url_for('resume'))

    form_state = build_resume_form_state(request.form) if request.method == 'POST' else get_saved_resume_state(user)
    resume_data = extract_resume_data(request.form) if request.method == 'POST' else session.get('resume_data')
    if not resume_data:
        flash('Please fill resume details first.', 'warning')
        return redirect(url_for('resume'))

    photo_filename = None
    if request.method == 'POST':
        incoming_photo = request.files.get('photo')
        incoming_data_url = request.form.get('photo_data_url')
        photo_filename = save_uploaded_photo(incoming_photo, incoming_data_url)
        if (incoming_data_url or getattr(incoming_photo, 'filename', '')) and not photo_filename:
            flash('Photo upload failed. Max size is 1 MB. Supported: PNG, JPG, JPEG, WEBP.', 'warning')
            return redirect(url_for('resume') + '#photo-upload-section')
        if not photo_filename:
            photo_filename = (session.get('resume_data') or {}).get('photo_filename') or user.profile_photo
        resume_data['photo_filename'] = photo_filename
        form_state['photo_filename'] = photo_filename

    template_source = (
        request.form.get('selected_template')
        if request.method == 'POST'
        else request.args.get('template') or resume_data.get('selected_template') or session.get('selected_template')
    )
    template_name = normalize_template_name(template_source)
    if template_requires_photo(template_name) and not resume_data.get('photo_filename'):
        flash('Please choose photo first.', 'warning')
        return redirect(url_for('resume'))
    resume_data['selected_template'] = template_name
    if request.method == 'GET':
        resume_data['template_customizations'] = get_template_customizations(template_name, request.args)
    saved_state = get_saved_resume_state(user) or {}
    if not (resume_data.get('section_orders') or {}):
        resume_data['section_orders'] = saved_state.get('section_orders') or {}
    if request.method != 'POST':
        resume_data = attach_resume_media(resume_data, preview_mode=True)
    session['selected_template'] = template_name
    session['resume_data'] = resume_data

    try:
        file_path = generate_resume_pdf(
            render_resume_pdf_html(resume_data),
            base_url=app.root_path,
        )
    except RuntimeError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('resume'))

    download_name = get_resume_download_name(resume_data, file_format, template_name=template_name)
    sync_user_resume_state(user, form_state, resume_data=resume_data, photo_filename=resume_data.get('photo_filename'))
    track_template_download(template_name)
    user.has_downloaded_resume = True
    user.last_resume_downloaded_at = datetime.utcnow()
    user.last_resume_download_name = download_name
    db.session.commit()
    return send_file(file_path, as_attachment=True, download_name=download_name)


@app.route('/feedback', methods=['POST'])
def feedback():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    current = get_primary_user(user.get('email'))
    if current:
        banned = enforce_not_banned(current)
        if banned:
            return banned

    comment = request.form.get('comment', '').strip()
    rating_raw = request.form.get('rating', '').strip()
    try:
        rating = int(rating_raw)
    except ValueError:
        flash('Please select a valid rating.', 'warning')
        return redirect(url_for('home'))

    if not comment:
        flash('Feedback comment cannot be empty.', 'warning')
        return redirect(url_for('home'))
    if rating < 1 or rating > 5:
        flash('Rating must be between 1 and 5.', 'warning')
        return redirect(url_for('home'))

    new_feedback = Feedback(user_email=user['email'], rating=rating, comment=comment)
    db.session.add(new_feedback)
    db.session.commit()
    flash('Thank you for your feedback.', 'success')
    return redirect(url_for('home'))


@app.route("/generate", methods=["POST"])
def generate():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = get_primary_user(session['user'].get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    form_state = build_resume_form_state(request.form)
    resume_data = extract_resume_data(request.form)
    photo_filename = save_uploaded_photo(request.files.get('photo'), request.form.get('photo_data_url'))
    if not photo_filename:
        photo_filename = (session.get('resume_data') or {}).get('photo_filename') or user.profile_photo
    template_name = normalize_template_name(request.form.get('selected_template') or resume_data.get('selected_template'))
    if template_requires_photo(template_name) and not photo_filename:
        flash('Please choose photo first.', 'warning')
        return redirect(url_for('resume'))
    resume_data['selected_template'] = template_name
    resume_data['photo_filename'] = photo_filename
    form_state['selected_template'] = template_name
    form_state['photo_filename'] = photo_filename
    session['selected_template'] = template_name
    session['resume_data'] = resume_data
    try:
        file_path = generate_resume_pdf(
            render_resume_pdf_html(resume_data),
            base_url=app.root_path,
        )
    except RuntimeError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('resume'))
    download_name = get_resume_download_name(resume_data, 'pdf', template_name=template_name)
    sync_user_resume_state(user, form_state, resume_data=resume_data, photo_filename=photo_filename)
    track_template_download(template_name)
    user.has_downloaded_resume = True
    user.last_resume_downloaded_at = datetime.utcnow()
    user.last_resume_download_name = download_name
    db.session.commit()
    return send_file(file_path, as_attachment=True, download_name=download_name)


@app.route('/account')
def account():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))
    user = get_primary_user(session_user.get('email'))
    if not user:
        session.pop('user', None)
        return redirect(url_for('login'))
    banned = enforce_not_banned(user)
    if banned:
        return banned

    saved_resume = get_saved_resume_state(user)
    account_name = (user.profile_name or '').strip()
    if not account_name:
        account_name = " ".join(
            part for part in [
                saved_resume.get('first_name', '').strip(),
                saved_resume.get('last_name', '').strip(),
            ] if part
        ) or 'My Account'
    return render_template(
        'account.html',
        user=user,
        saved_resume=saved_resume,
        profile_photo_src=get_photo_src(user.profile_photo, preview_mode=True),
        account_name=account_name,
        has_password=bool(user.password),
    )


@app.route('/logout')
def logout():
    session.pop('_flashes', None)
    session.pop('user', None)
    return redirect(url_for('home'))


# ---- Admin Panel ----

def _safe_next_url(value):
    raw = (value or '').strip()
    if not raw:
        return None
    if raw.startswith('/') and not raw.startswith('//'):
        return raw
    return None


@app.before_request
def _maintenance_mode_guard():
    if request.path.startswith('/static/') or request.path.startswith('/uploaded-photos/'):
        return None

    try:
        apply_runtime_env_overrides()
    except Exception:
        pass

    if request.path.startswith('/admin'):
        return None
    if not is_truthy(get_setting_value('maintenance_mode', '0')):
        return None

    blocked_prefixes = (
        '/resume',
        '/preview',
        '/export',
        '/generate',
        '/api/ai/',
    )
    if request.path.startswith(blocked_prefixes):
        flash('The site is under maintenance. Please try again later.', 'warning')
        return redirect(url_for('home'))
    return None


@app.route('/admin')
def admin_root():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = normalize_email(request.form.get('email'))
        password = request.form.get('password', '')
        admin = Admin.query.filter(func.lower(Admin.email) == email).first()
        if not admin or not admin.is_active or not check_password_hash(admin.password_hash, password):
            flash('Invalid admin email or password.', 'danger')
            return render_template('admin/login.html', prefill_email=email)

        admin.last_login_at = datetime.utcnow()
        db.session.commit()
        session['admin'] = {'email': admin.email}
        log_admin_action(admin.email, 'Logged in')
        next_url = _safe_next_url(request.args.get('next') or request.form.get('next'))
        return redirect(next_url or url_for('admin_dashboard'))

    prefill_email = normalize_email(request.args.get('email'))
    return render_template('admin/login.html', prefill_email=prefill_email)


@app.route('/admin/logout')
def admin_logout():
    admin_session = session.get('admin') or {}
    admin_email = (admin_session.get('email') or '').strip().lower()
    session.pop('admin', None)
    if admin_email:
        log_admin_action(admin_email, 'Logged out')
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    stats = get_stats()
    return render_template('admin/dashboard.html', stats=stats, admin=session.get('admin'))


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin/users.html', users=users, admin=session.get('admin'))


@app.route('/admin/users/<int:user_id>')
@admin_required
def admin_user_view(user_id):
    user = User.query.get_or_404(user_id)
    saved_resume = None
    if user.saved_resume_data:
        try:
            saved_resume = json.loads(user.saved_resume_data)
        except Exception:
            saved_resume = user.saved_resume_data
    feedback_entries = Feedback.query.filter(func.lower(Feedback.user_email) == normalize_email(user.email)).order_by(Feedback.created_at.desc()).all()
    return render_template('admin/user_view.html', user=user, saved_resume=saved_resume, feedback_entries=feedback_entries, admin=session.get('admin'))


@app.route('/admin/users/<int:user_id>/ban', methods=['POST'])
@admin_required
def admin_user_ban(user_id):
    user = User.query.get_or_404(user_id)
    reason = (request.form.get('reason') or '').strip()
    user.is_banned = True
    user.banned_at = datetime.utcnow()
    user.ban_reason = reason[:255] if reason else None
    db.session.commit()
    log_admin_action((session.get('admin') or {}).get('email'), f'Banned user {user.email}')
    flash('User banned.', 'success')
    return redirect(request.referrer or url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/unban', methods=['POST'])
@admin_required
def admin_user_unban(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.banned_at = None
    user.ban_reason = None
    db.session.commit()
    log_admin_action((session.get('admin') or {}).get('email'), f'Unbanned user {user.email}')
    flash('User unbanned.', 'success')
    return redirect(request.referrer or url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_user_delete(user_id):
    user = User.query.get_or_404(user_id)
    email = normalize_email(user.email)
    Feedback.query.filter(func.lower(Feedback.user_email) == email).delete(synchronize_session=False)
    PendingSignup.query.filter(func.lower(PendingSignup.email) == email).delete(synchronize_session=False)
    PendingLogin.query.filter(func.lower(PendingLogin.email) == email).delete(synchronize_session=False)
    PendingPasswordReset.query.filter(func.lower(PendingPasswordReset.email) == email).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    log_admin_action((session.get('admin') or {}).get('email'), f'Deleted user {email}')
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/resumes')
@admin_required
def admin_resumes():
    users = User.query.filter(User.last_resume_downloaded_at.isnot(None)).order_by(User.last_resume_downloaded_at.desc()).all()
    rows = []
    for u in users:
        template_used = ''
        name = (u.last_resume_download_name or '').lower()
        match = re.search(r'template-(\\d+)', name)
        if match:
            template_used = match.group(1)
        rows.append(
            {
                'id': u.id,
                'email': u.email,
                'template': template_used,
                'download_name': u.last_resume_download_name,
                'downloaded_at': u.last_resume_downloaded_at,
            }
        )
    return render_template('admin/resumes.html', rows=rows, admin=session.get('admin'))


@app.route('/admin/feedback')
@admin_required
def admin_feedback():
    rating = (request.args.get('rating') or '').strip()
    query = Feedback.query
    if rating.isdigit():
        query = query.filter(Feedback.rating == int(rating))
    feedback_entries = query.order_by(Feedback.created_at.desc()).all()
    return render_template('admin/feedback.html', feedback_entries=feedback_entries, selected_rating=rating, admin=session.get('admin'))


@app.route('/admin/feedback/<int:feedback_id>/delete', methods=['POST'])
@admin_required
def admin_feedback_delete(feedback_id):
    entry = Feedback.query.get_or_404(feedback_id)
    db.session.delete(entry)
    db.session.commit()
    log_admin_action((session.get('admin') or {}).get('email'), f'Deleted feedback #{feedback_id}')
    flash('Feedback deleted.', 'success')
    return redirect(request.referrer or url_for('admin_feedback'))


def _date_key(dt_value):
    if not dt_value:
        return None
    return dt_value.strftime('%Y-%m-%d')


@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    days = 14
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    labels = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]

    user_counts = {label: 0 for label in labels}
    for day_value, count in db.session.query(func.date(User.created_at), func.count(User.id)).group_by(func.date(User.created_at)).all():
        label = str(day_value)
        if label in user_counts:
            user_counts[label] = int(count)

    resume_counts = {label: 0 for label in labels}
    resumes_dir = get_resumes_dir()
    if os.path.isdir(resumes_dir):
        for filename in os.listdir(resumes_dir):
            path = os.path.join(resumes_dir, filename)
            if not os.path.isfile(path):
                continue
            try:
                dt_value = datetime.utcfromtimestamp(os.path.getmtime(path))
            except Exception:
                continue
            key = _date_key(dt_value)
            if key in resume_counts:
                resume_counts[key] += 1

    rating_counts = {str(i): 0 for i in range(1, 6)}
    for rating_value, count in db.session.query(Feedback.rating, func.count(Feedback.id)).group_by(Feedback.rating).all():
        if rating_value is None:
            continue
        rating_counts[str(int(rating_value))] = int(count)

    payload = {
        'labels': labels,
        'users_per_day': [user_counts[l] for l in labels],
        'resumes_per_day': [resume_counts[l] for l in labels],
        'ratings': [rating_counts[str(i)] for i in range(1, 6)],
    }
    return render_template('admin/analytics.html', analytics=payload, admin=session.get('admin'))


@app.route('/admin/templates')
@admin_required
def admin_templates():
    templates = [str(i) for i in range(1, 10)]
    download_counts = {t: 0 for t in templates}
    for row in TemplateUsage.query.all():
        template_value = normalize_template_name(getattr(row, 'template_name', '1'))
        download_counts[template_value] = int(getattr(row, 'downloads', 0) or 0)

    saved_counts = {t: 0 for t in templates}
    for u in User.query.filter(User.saved_resume_data.isnot(None)).all():
        raw = (u.saved_resume_data or '').strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        template_value = normalize_template_name(parsed.get('selected_template'))
        saved_counts[template_value] += 1

    items = []
    for template_value in templates:
        downloads = download_counts.get(template_value, 0)
        saved = saved_counts.get(template_value, 0)
        uses = downloads if downloads > 0 else saved
        items.append({'template': template_value, 'uses': uses, 'downloads': downloads, 'saved': saved})

    items.sort(key=lambda x: int(x['template']))
    return render_template('admin/templates.html', items=items, admin=session.get('admin'))


@app.route('/admin/files')
@admin_required
def admin_files():
    resumes_dir = get_resumes_dir()
    files = []
    if os.path.isdir(resumes_dir):
        for filename in os.listdir(resumes_dir):
            path = os.path.join(resumes_dir, filename)
            if not os.path.isfile(path):
                continue
            try:
                stat = os.stat(path)
            except Exception:
                continue
            files.append(
                {
                    'name': filename,
                    'size': stat.st_size,
                    'modified_at': datetime.utcfromtimestamp(stat.st_mtime),
                }
            )
    files.sort(key=lambda x: x['modified_at'] or datetime.min, reverse=True)
    return render_template('admin/files.html', files=files, resumes_dir=resumes_dir, admin=session.get('admin'))


@app.route('/admin/files/download/<path:filename>')
@admin_required
def admin_files_download(filename):
    resumes_dir = get_resumes_dir()
    safe_name = os.path.basename(filename)
    return send_from_directory(resumes_dir, safe_name, as_attachment=True)


@app.route('/admin/files/delete/<path:filename>', methods=['POST'])
@admin_required
def admin_files_delete(filename):
    resumes_dir = get_resumes_dir()
    safe_name = os.path.basename(filename)
    path = os.path.join(resumes_dir, safe_name)
    if not os.path.isfile(path):
        flash('File not found.', 'warning')
        return redirect(url_for('admin_files'))
    try:
        os.remove(path)
    except Exception as exc:
        flash(f'Could not delete file: {str(exc)}', 'danger')
        return redirect(url_for('admin_files'))
    log_admin_action((session.get('admin') or {}).get('email'), f'Deleted resume file {safe_name}')
    flash('File deleted.', 'success')
    return redirect(url_for('admin_files'))


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    keys = [
        'maintenance_mode',
        'smtp_host',
        'smtp_port',
        'smtp_username',
        'smtp_password',
        'smtp_sender',
        'smtp_use_tls',
        'smtp_use_ssl',
        'ai_provider',
        'openai_api_key',
        'openai_model',
        'google_api_key',
        'google_model',
        'groq_api_key',
        'groq_model',
    ]
    if request.method == 'POST':
        for key in keys:
            value = (request.form.get(key) or '').strip()
            existing = AdminSetting.query.filter(AdminSetting.key == key).first()
            if existing:
                existing.value = value
                existing.updated_at = datetime.utcnow()
            else:
                db.session.add(AdminSetting(key=key, value=value, updated_at=datetime.utcnow()))
        db.session.commit()
        log_admin_action((session.get('admin') or {}).get('email'), 'Updated settings')
        flash('Settings saved.', 'success')
        return redirect(url_for('admin_settings'))

    values = {key: get_setting_value(key, '') for key in keys}
    values['ai_provider'] = values['ai_provider'] or (os.getenv('AI_PROVIDER') or '').strip()
    values['openai_api_key'] = values['openai_api_key'] or (os.getenv('OPENAI_API_KEY') or '').strip()
    values['openai_model'] = values['openai_model'] or (os.getenv('OPENAI_MODEL') or '').strip()
    values['google_api_key'] = values['google_api_key'] or (os.getenv('GOOGLE_API_KEY') or '').strip()
    values['google_model'] = values['google_model'] or (os.getenv('GOOGLE_MODEL') or '').strip()
    values['groq_api_key'] = values['groq_api_key'] or (os.getenv('GROQ_API_KEY') or '').strip()
    values['groq_model'] = values['groq_model'] or (os.getenv('GROQ_MODEL') or '').strip()
    return render_template('admin/settings.html', values=values, admin=session.get('admin'))


@app.route('/admin/logs')
@admin_required
def admin_logs():
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(200).all()
    return render_template('admin/logs.html', logs=logs, admin=session.get('admin'))


# AI Integration Routes
@app.route('/api/ai/generate-bullets', methods=['POST'])
def ai_generate_bullets():
    """Generate professional bullet points for a job role."""
    try:
        data = request.json
        job_title = data.get('job_title', '').strip()
        skills = [s.strip() for s in (data.get('skills', []) or []) if s.strip()]
        num_bullets = min(int(data.get('num_bullets', 3)), 10)
        kind = (data.get('kind', 'experience') or 'experience').strip().lower()
        context = data.get('context', '') or ''
        target_job_description = data.get('job_description', '') or ''
        keywords = data.get('keywords', []) or []
        
        if not job_title:
            return jsonify({'error': 'Job title is required'}), 400
        
        bullets = generate_bullet_points(
            job_title,
            skills,
            num_bullets,
            kind=kind,
            context=context,
            target_job_description=target_job_description,
            keywords=keywords,
        )
        return jsonify({'bullets': bullets})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500


@app.route('/api/ai/optimize-content', methods=['POST'])
def ai_optimize_content():
    """Optimize resume content for ATS and readability."""
    try:
        data = request.json
        resume_text = data.get('resume_text', '').strip()
        job_description = data.get('job_description', '').strip()
        
        if not resume_text:
            return jsonify({'error': 'Resume text is required'}), 400
        
        optimized = optimize_resume_content(resume_text, job_description)
        return jsonify({'optimized_content': optimized})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Optimization failed: {str(e)}'}), 500


@app.route('/api/ai/extract-skills', methods=['POST'])
def ai_extract_skills():
    """Extract skills from a job description."""
    try:
        data = request.json
        job_description = data.get('job_description', '').strip()
        category = data.get('category', 'all')
        
        if not job_description:
            return jsonify({'error': 'Job description is required'}), 400
        
        if category not in ['technical', 'soft', 'all']:
            category = 'all'
        
        skills = extract_skills(job_description, category)
        return jsonify({'skills': skills})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Skill extraction failed: {str(e)}'}), 500


@app.route('/api/ai/organize-technical-skills', methods=['POST'])
def ai_organize_technical_skills():
    """Organize a flat technical skills list into categorized ATS-friendly lines."""
    try:
        data = request.json or {}
        technical_skills = (data.get('technical_skills', '') or '').strip()
        user_prompt = (data.get('user_prompt', '') or '').strip()
        if not technical_skills:
            return jsonify({'error': 'Technical skills are required'}), 400
        organized = organize_technical_skills(technical_skills=technical_skills, user_prompt=user_prompt)
        return jsonify({'organized': organized})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Organize failed: {str(e)}'}), 500


@app.route('/api/ai/generate-summary', methods=['POST'])
def ai_generate_summary():
    """Generate a professional profile summary."""
    try:
        data = request.json
        name = data.get('name', '').strip()
        job_title = data.get('job_title', '').strip()
        years_experience = int(data.get('years_experience', 0))
        skills = [s.strip() for s in (data.get('skills', []) or []) if s.strip()]
        
        if not name or not job_title:
            return jsonify({'error': 'Name and job title are required'}), 400
        
        summary = generate_profile_summary(name, job_title, years_experience, skills)
        return jsonify({'summary': summary})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Summary generation failed: {str(e)}'}), 500


@app.route('/api/ai/improve-description', methods=['POST'])
def ai_improve_description():
    """Improve a job description or work experience bullet point."""
    try:
        data = request.json
        description = data.get('description', '').strip()
        
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        
        improved = improve_job_description(description)
        return jsonify({'improved_description': improved})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Improvement failed: {str(e)}'}), 500


@app.route('/api/ai/summarize', methods=['POST'])
def ai_summarize():
    """Summarize project/experience text into resume-friendly sentences."""
    try:
        data = request.json
        text_value = (data.get('text', '') or '').strip()
        kind = (data.get('kind', 'general') or 'general').strip().lower()
        max_sentences = int(data.get('max_sentences', 2))

        if not text_value:
            return jsonify({'error': 'Text is required'}), 400

        summary = summarize_text(text_value, kind=kind, max_sentences=max_sentences)
        return jsonify({'summary': summary})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {str(e)}'}), 500


@app.route('/api/ai/apply-ai', methods=['POST'])
def ai_apply_ai():
    """
    Apply AI to summary + all project descriptions + all experience responsibilities.
    Returns a structured payload so the frontend can update fields in-place.
    """
    try:
        data = request.json or {}
        job_title = (data.get('job_title', '') or '').strip()
        experience = (data.get('experience', '') or '').strip()
        skills = (data.get('skills', '') or '').strip()
        # Legacy endpoint: keep behavior stable but default to 3 concise lines.
        bullet_count = 2

        projects = data.get('projects', []) or []
        experiences = data.get('experiences', []) or []

        if not job_title:
            return jsonify({'error': 'Job title is required'}), 400

        summary = generate_ats_resume_summary(job_title=job_title, experience=experience, skills=skills)

        project_results = []
        for project in projects:
            project_name = (project.get('project_name', '') or '').strip()
            technologies = (project.get('technologies', '') or '').strip()
            project_details = (project.get('project_details', '') or '').strip()
            if not (project_name or technologies or project_details):
                project_results.append('')
                continue
            project_results.append(
                generate_ats_project_bullets(
                    project_name=project_name,
                    technologies=technologies,
                    project_details=project_details,
                    bullet_count=bullet_count,
                )
            )

        experience_results = []
        for exp in experiences:
            exp_job_title = (exp.get('job_title', '') or '').strip() or job_title
            company_type = (exp.get('company_type', '') or '').strip()
            technologies = (exp.get('technologies', '') or '').strip()
            responsibilities = (exp.get('responsibilities', '') or '').strip()
            if not (exp_job_title or company_type or technologies or responsibilities):
                experience_results.append('')
                continue
            experience_results.append(
                generate_ats_experience_bullets(
                    job_title=exp_job_title,
                    company_type=company_type,
                    technologies=technologies,
                    responsibilities=responsibilities,
                    bullet_count=bullet_count,
                )
            )

        return jsonify(
            {
                'summary': summary,
                'projects': project_results,
                'experiences': experience_results,
            }
        )
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Apply AI failed: {str(e)}'}), 500


@app.route('/api/ai/ats-summary', methods=['POST'])
def ai_ats_summary():
    """Generate an ATS-friendly professional summary for the resume header."""
    try:
        data = request.json or {}
        job_title = (data.get('job_title', '') or '').strip()
        experience = (data.get('experience', '') or '').strip()
        skills = (data.get('skills', '') or '').strip()
        user_prompt = (data.get('user_prompt', '') or '').strip()
        if not job_title:
            return jsonify({'error': 'Job title is required'}), 400
        summary = generate_ats_resume_summary(job_title=job_title, experience=experience, skills=skills, user_prompt=user_prompt)
        return jsonify({'summary': summary})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500


@app.route('/api/ai/ats-project', methods=['POST'])
def ai_ats_project():
    """Generate ATS-friendly project bullets (one line per bullet)."""
    try:
        data = request.json or {}
        project_name = (data.get('project_name', '') or '').strip()
        technologies = (data.get('technologies', '') or '').strip()
        project_details = (data.get('project_details', '') or '').strip()
        user_prompt = (data.get('user_prompt', '') or '').strip()
        if not (project_name or technologies or project_details):
            return jsonify({'error': 'Project title, technologies, or details are required'}), 400
        bullets = generate_ats_project_bullets(
            project_name=project_name,
            technologies=technologies,
            project_details=project_details,
            bullet_count=2,
            user_prompt=user_prompt,
        )
        return jsonify({'bullets': bullets})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500


@app.route('/api/ai/ats-experience', methods=['POST'])
def ai_ats_experience():
    """Generate ATS-friendly experience bullets (one line per bullet)."""
    try:
        data = request.json or {}
        job_title = (data.get('job_title', '') or '').strip()
        company_type = (data.get('company_type', '') or '').strip()
        technologies = (data.get('technologies', '') or '').strip()
        responsibilities = (data.get('responsibilities', '') or '').strip()
        user_prompt = (data.get('user_prompt', '') or '').strip()
        if not (job_title or company_type or technologies or responsibilities):
            return jsonify({'error': 'Role/company/skills/responsibilities are required'}), 400
        bullets = generate_ats_experience_bullets(
            job_title=job_title,
            company_type=company_type,
            technologies=technologies,
            responsibilities=responsibilities,
            bullet_count=2,
            user_prompt=user_prompt,
        )
        return jsonify({'bullets': bullets})
    except ValueError as e:
        return jsonify({'error': f'Configuration error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500


def _strip_numbered_prefix(line, prefix_word):
    value = (line or '').strip()
    if ':' not in value:
        return value
    left, right = value.split(':', 1)
    left = left.strip().lower()
    if left.startswith(prefix_word.lower()):
        return right.strip()
    return value


def parse_project_desc_to_entries(project_desc):
    blocks = [block.strip() for block in (project_desc or '').split('\n\n') if block.strip()]
    entries = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        title = _strip_numbered_prefix(lines[0], 'project')
        tech = ''
        body_lines = []
        for line in lines[1:]:
            if line.lower().startswith('technologies:'):
                tech = line.split(':', 1)[1].strip()
                continue
            body_lines.append(line.lstrip('- ').lstrip('• ').strip())
        desc = "\n".join([l for l in body_lines if l]).strip()
        if title or tech or desc:
            entries.append({'title': title, 'tech': tech, 'desc': desc})
    return entries


def parse_experience_desc_to_entries(experience_desc):
    blocks = [block.strip() for block in (experience_desc or '').split('\n\n') if block.strip()]
    entries = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = _strip_numbered_prefix(lines[0], 'experience')
        role = ''
        company = ''
        if ' - ' in header:
            role, company = [part.strip() for part in header.split(' - ', 1)]
        else:
            role = header.strip()
        duration = ''
        body_lines = []
        for line in lines[1:]:
            if line.lower().startswith('duration:'):
                duration = line.split(':', 1)[1].strip()
                continue
            body_lines.append(line.lstrip('- ').lstrip('• ').strip())
        desc = "\n".join([l for l in body_lines if l]).strip()
        if role or company or duration or desc:
            entries.append({'role': role, 'company': company, 'duration': duration, 'desc': desc})
    return entries


@app.route('/api/preview/save-fields', methods=['POST'])
def preview_save_fields():
    """Persist inline edits from the preview (used by Canva-like editor)."""
    try:
        session_user = session.get('user')
        if not session_user:
            return jsonify({'error': 'Unauthorized'}), 401

        user = get_primary_user(session_user.get('email'))
        if not user:
            session.pop('user', None)
            return jsonify({'error': 'Unauthorized'}), 401

        payload = request.json or {}
        fields = payload.get('fields') or {}
        if not isinstance(fields, dict):
            return jsonify({'error': 'Invalid fields'}), 400

        allowed = {
            'full_name',
            'job_title',
            'email',
            'phone',
            'location',
            'summary',
            'technical_skills',
            'soft_skills',
            'achievements',
            'project_desc',
            'experience_desc',
        }

        saved_state = get_saved_resume_state(user)
        resume_data = session.get('resume_data') or {}
        if not isinstance(resume_data, dict):
            resume_data = {}

        for key, value in fields.items():
            if key not in allowed:
                continue
            if value is None:
                value = ''
            if not isinstance(value, str):
                value = str(value)
            fields[key] = value.strip()

        full_name = fields.get('full_name')
        if full_name is not None:
            parts = [part for part in full_name.split() if part]
            if parts:
                saved_state['first_name'] = parts[0]
                saved_state['last_name'] = parts[-1] if len(parts) > 1 else ''
                saved_state['middle_name'] = " ".join(parts[1:-1]) if len(parts) > 2 else ''
            saved_state['job_title'] = saved_state.get('job_title', '')
            resume_data['full_name'] = full_name

        for simple_key in ['job_title', 'email', 'phone', 'location', 'summary', 'technical_skills', 'soft_skills']:
            if simple_key in fields:
                saved_state[simple_key] = fields[simple_key]
                resume_data[simple_key] = fields[simple_key]

        if 'achievements' in fields:
            achievement_items = [
                item.strip().lstrip('- ').strip()
                for item in (fields.get('achievements') or '').splitlines()
                if item.strip()
            ]
            saved_state['achievement_items'] = achievement_items
            resume_data['achievements'] = "\n".join(f'- {item}' for item in achievement_items) if achievement_items else ''

        if 'project_desc' in fields:
            resume_data['project_desc'] = fields['project_desc']
            saved_state['project_entries'] = parse_project_desc_to_entries(fields['project_desc'])

        if 'experience_desc' in fields:
            resume_data['experience_desc'] = fields['experience_desc']
            saved_state['experience_entries'] = parse_experience_desc_to_entries(fields['experience_desc'])

        session['resume_data'] = resume_data
        sync_user_resume_state(user, saved_state, resume_data=resume_data, photo_filename=resume_data.get('photo_filename'))
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'}), 500


## Canvas mode endpoints removed (preview-only feature).
if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host="0.0.0.0", port=5000)
