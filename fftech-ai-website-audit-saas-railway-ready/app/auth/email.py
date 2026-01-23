
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode
import requests
from ..settings import get_settings

settings = get_settings()

def _html_body(login_url: str) -> str:
    return f"""
    <p>Hello,</p>
    <p>Click the secure link below to sign in:</p>
    <p><a href='{login_url}'>{login_url}</a></p>
    <p>This link expires in {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes.</p>
    <p>- {settings.BRAND_NAME}</p>
    """

def _send_via_resend(to_email: str, subject: str, html: str):
    api_key = settings.RESEND_API_KEY
    from_addr = settings.RESEND_FROM or settings.MAIL_FROM
    if not api_key or not from_addr:
        raise RuntimeError('Resend API key or from address missing')
    r = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}','Content-Type':'application/json'},
        json={'from': from_addr,'to': to_email,'subject': subject,'html': html},
        timeout=15
    )
    r.raise_for_status()

def _send_via_smtp(to_email: str, subject: str, html: str):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.MAIL_FROM
    msg['To'] = to_email
    msg.attach(MIMEText(html, 'html'))
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
        s.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        s.sendmail(settings.MAIL_FROM, [to_email], msg.as_string())

def send_magic_link(to_email: str, token: str):
    login_url = f"{settings.BASE_URL}/auth/magic?" + urlencode({"token": token})
    subject = f"{settings.APP_NAME} - Secure Sign-in Link"
    html = _html_body(login_url)
    provider = (settings.EMAIL_PROVIDER or 'auto').lower()
    if provider == 'resend' or (provider == 'auto' and settings.RESEND_API_KEY):
        if settings.RESEND_ENFORCE_DKIM:
            try:
                res = requests.get('https://api.resend.com/domains', headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'}, timeout=10)
                res.raise_for_status()
                data = res.json().get('data', [])
                domain = (settings.RESEND_DOMAIN or '').lower()
                found = next((d for d in data if d.get('name','').lower()==domain), None)
                if not found or found.get('status') != 'verified':
                    raise RuntimeError('Resend DKIM not verified for domain; email blocked by policy')
            except Exception as e:
                raise RuntimeError(f'DKIM check failed: {e}')
        _send_via_resend(to_email, subject, html)
    else:
        _send_via_smtp(to_email, subject, html)
