import os
from flask import Blueprint, redirect, url_for, session, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from authlib.integrations.flask_client import OAuth
from modules.database import SessionLocal
from modules.models import User

auth_bp = Blueprint('auth', __name__)
oauth = OAuth()
login_manager = LoginManager()


class LoginUser(UserMixin):
    """Flask-Login 用的輕量包裝，避免 session 裡存整個 ORM 物件"""
    def __init__(self, user: User):
        self.id       = user.id
        self.email    = user.email
        self.name     = user.name
        self.role     = user.role
        self.max_stocks = user.max_stocks

    @property
    def is_admin(self):
        return self.role == 'admin'


def init_auth(app):
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    @login_manager.user_loader
    def load_user(user_id):
        db = SessionLocal()
        try:
            user = db.get(User, int(user_id))
            return LoginUser(user) if user else None
        finally:
            db.close()

    app.register_blueprint(auth_bp)


# ── 路由 ──────────────────────────────────────────────

@auth_bp.route('/login')
def login():
    redirect_uri = url_for('auth.callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


def _email_allowed(email, allowed_env: str) -> bool:
    """§四十四 S2：ALLOWED_EMAILS allowlist（逗號分隔、不分大小寫）。
    未設定（空/空白）→ 開放（向後相容，避免鎖死既有用戶）；
    設定後所有登入（含既有帳號）都須在清單內。"""
    allowed = (allowed_env or '').strip()
    if not allowed:
        return True
    allow_set = {e.strip().lower() for e in allowed.split(',') if e.strip()}
    return (email or '').lower() in allow_set


@auth_bp.route('/auth/callback')
def callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        return '登入失敗', 400

    # §四十四 S2：OAuth allowlist（7/12 健檢 🔴 #2 — 原任何 Google 帳號
    # 可自動建帳號消耗 AI 額度）。ALLOWED_EMAILS 未設定 → 維持開放 + 警告。
    _allow_env = os.getenv('ALLOWED_EMAILS', '')
    if not _allow_env.strip():
        print('[auth] 警告：ALLOWED_EMAILS 未設定，OAuth 註冊完全開放')
    elif not _email_allowed(user_info.get('email', ''), _allow_env):
        print(f"[auth] 拒絕未授權登入: {user_info.get('email', '(無 email)')}")
        return '此帳號未獲授權使用本系統，請聯絡管理員', 403

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(google_id=user_info['sub']).first()

        if not user:
            # 判斷是否為管理者（第一個註冊或 email 符合）
            admin_email = os.getenv('ADMIN_EMAIL', '')
            is_first   = db.query(User).count() == 0
            role = 'admin' if (is_first or user_info['email'] == admin_email) else 'user'

            user = User(
                google_id=user_info['sub'],
                email=user_info['email'],
                name=user_info['name'],
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        login_user(LoginUser(user))
        return redirect('/dashboard')
    finally:
        db.close()


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect('/')
