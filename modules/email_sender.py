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
        body = f'您好，\n\n今日投資建議報表已產生，請見附件。\n\n本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n祝投資順利！'

    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # 附加 HTML 報表
    if os.path.exists(report_path):
        with open(report_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(report_path)
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

def send_weekly_report(report_path):
    subject = f'投資建議週報 {datetime.now().strftime("%Y/%m/%d")}'
    body = f'您好，\n\n本週投資建議週報已產生，請見附件。\n\n本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n祝投資順利！'
    return send_report(report_path, subject, body)