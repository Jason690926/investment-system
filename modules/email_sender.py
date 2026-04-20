import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import config

# ── HTML 轉 PDF ───────────────────────────────────────────
def html_to_pdf(html_path):
    """用 weasyprint 把 HTML 轉成 PDF，回傳 PDF 路徑"""
    pdf_path = html_path.replace('.html', '.pdf')
    try:
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(pdf_path)
        print(f'PDF 已產生：{pdf_path}')
        return pdf_path
    except Exception as e:
        print(f'PDF 轉換失敗，改用 HTML: {e}')
        return None

# ── 寄送報表 ──────────────────────────────────────────────
def send_report(report_path, subject=None, body=None):
    if subject is None:
        subject = f'投資建議晨報 {datetime.now().strftime("%Y/%m/%d")}'
    if body is None:
        body = (
            '您好，\n\n'
            '今日投資建議報表已產生，請見附件 PDF。\n\n'
            '本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n'
            '祝投資順利！'
        )

    # 嘗試轉 PDF，失敗則用原始 HTML
    pdf_path = html_to_pdf(report_path)
    attach_path = pdf_path if pdf_path else report_path
    attach_mime = 'application/pdf' if pdf_path else 'application/octet-stream'

    return _send_email(subject, body, attach_path, attach_mime)

def send_weekly_report(report_path):
    subject = f'投資建議週報 {datetime.now().strftime("%Y/%m/%d")}'
    body = (
        '您好，\n\n'
        '本週投資建議週報已產生，請見附件 PDF。\n\n'
        '本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n'
        '祝投資順利！'
    )
    return send_report(report_path, subject, body)

# ── 內部 Email 發送 ───────────────────────────────────────
def _send_email(subject, body, attach_path, attach_mime='application/pdf'):
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if attach_path and os.path.exists(attach_path):
        with open(attach_path, 'rb') as f:
            part = MIMEBase(*attach_mime.split('/'))
            part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(attach_path)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print(f'Email 已寄送至 {config.EMAIL_RECEIVER}')
        return True
    except Exception as e:
        print(f'Email 寄送失敗: {e}')
        return False
