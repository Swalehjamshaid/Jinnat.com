
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from ..settings import get_settings

def send_email_with_attachments(to_email: str, subject: str, html_body: str, attachments: list[str] = None):
    settings = get_settings()
    msg = MIMEMultipart()
    msg['From'] = settings.MAIL_FROM
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))
    for f in attachments or []:
        p = Path(f)
        if not p.exists():
            continue
        with open(p, 'rb') as fp:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(fp.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{p.name}"')
        msg.attach(part)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
        s.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        s.sendmail(settings.MAIL_FROM, [to_email], msg.as_string())
