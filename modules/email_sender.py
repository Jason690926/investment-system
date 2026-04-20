import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import config

def send_report(report_path, subject=None, body=None):
    if subject is None:
        subject = f'投資建議晨報 {datetime.now().strftime("%Y/%m/%d")}'
    if body is None:
        body = (
            '您好，\n\n'
            '今日投資建議報表已產生，請見附件。\n'
            '用瀏覽器開啟附件可完整顯示圖表與格式。\n'
            '若需要 PDF，在瀏覽器開啟後按 Ctrl+P → 另存為 PDF。\n\n'
            '本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n'
            '祝投資順利！'
        )
    return _send_email(subject, body, report_path)

def send_weekly_report(report_path):
    subject = f'投資建議週報 {datetime.now().strftime("%Y/%m/%d")}'
    body = (
        '您好，\n\n'
        '本週投資建議週報已產生，請見附件。\n'
        '用瀏覽器開啟附件可完整顯示圖表與格式。\n'
        '若需要 PDF，在瀏覽器開啟後按 Ctrl+P → 另存為 PDF。\n\n'
        '本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n'
        '祝投資順利！'
    )
    return _send_email(subject, body, report_path)

def _send_email(subject, body, attach_path):
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if attach_path and os.path.exists(attach_path):
        with open(attach_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
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
