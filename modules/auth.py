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


@auth_bp.route('/auth/callback')
def callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        return '登入失敗', 400

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
        return redirect('/')
    finally:
        db.close()


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')
