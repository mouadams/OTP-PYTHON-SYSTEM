import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _html(otp_code: str, purpose: str, expiry: int) -> str:
    titles = {
        "registration":   ("Verify Your Email",      "Complete your registration by entering the code below."),
        "password_reset": ("Reset Your Password",    "Use this code to reset your password."),
        "email_change":   ("Confirm Email Change",   "Enter this code to confirm your new email address."),
        "2fa":            ("Two-Factor Auth Code",   "Your two-factor authentication code is below."),
    }
    title, subtitle = titles.get(purpose, ("Verification Code", "Use the code below to continue."))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;color:#1a1a2e}}
  .wrap{{max-width:580px;margin:40px auto;padding:0 16px}}
  .card{{background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.10)}}
  .header{{background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:40px;text-align:center}}
  .header .logo{{font-size:28px;margin-bottom:8px}}
  .header h1{{color:#fff;font-size:22px;font-weight:700;letter-spacing:-.3px}}
  .header p{{color:rgba(255,255,255,.8);font-size:13px;margin-top:6px}}
  .body{{padding:40px}}
  .greeting{{font-size:15px;color:#444;line-height:1.6;margin-bottom:28px}}
  .otp-wrap{{text-align:center;margin:0 0 28px}}
  .otp-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#888;margin-bottom:12px}}
  .otp-code{{display:inline-block;background:#f3f0ff;border:2px dashed #7c3aed;border-radius:12px;padding:20px 48px;font-size:44px;font-weight:900;letter-spacing:12px;color:#4f46e5;font-family:'Courier New',monospace}}
  .expiry{{background:#fffbeb;border-left:4px solid #f59e0b;border-radius:4px;padding:12px 16px;font-size:13px;color:#92400e;margin-bottom:24px}}
  .expiry strong{{color:#b45309}}
  .notice{{background:#f9fafb;border-radius:8px;padding:16px 20px;font-size:13px;color:#6b7280;line-height:1.7}}
  .notice strong{{color:#374151}}
  .notice ul{{padding-left:18px;margin-top:6px}}
  .notice li{{margin-bottom:3px}}
  .footer{{border-top:1px solid #f0f0f0;padding:24px 40px;text-align:center;font-size:12px;color:#aaa;line-height:1.8}}
  @media(max-width:480px){{.body,.footer{{padding:28px 20px}}.otp-code{{font-size:32px;letter-spacing:6px;padding:16px 28px}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="header">
      <div class="logo">🔐</div>
      <h1>{title}</h1>
      <p>{settings.APP_NAME} · Secure Verification</p>
    </div>
    <div class="body">
      <p class="greeting">{subtitle}</p>
      <div class="otp-wrap">
        <p class="otp-label">Your verification code</p>
        <div class="otp-code">{otp_code}</div>
      </div>
      <div class="expiry">
        ⏱ This code expires in <strong>{expiry} minutes</strong>. Do not share it with anyone.
      </div>
      <div class="notice">
        <strong>🛡 Security Notice</strong>
        <ul>
          <li>If you did not request this, please ignore this email.</li>
          <li>{settings.APP_NAME} will <strong>never</strong> ask for your OTP.</li>
          <li>Only enter this code on <strong>{settings.APP_NAME}</strong>.</li>
        </ul>
      </div>
    </div>
    <div class="footer">
      Automated message — do not reply directly.<br>
      © 2024 {settings.APP_NAME} · Sent securely via Gmail SMTP
    </div>
  </div>
</div>
</body>
</html>"""


def _plain(otp_code: str, purpose: str, expiry: int) -> str:
    return (
        f"{settings.APP_NAME} — Verification Code\n"
        f"{'=' * 40}\n\n"
        f"Your {purpose.replace('_', ' ')} code: {otp_code}\n\n"
        f"Expires in {expiry} minutes.\n"
        f"Never share this code with anyone.\n"
    )


class EmailService:

    def send_otp_email(
        self,
        recipient_email: str,
        otp_code: str,
        purpose: str = "registration",
        expiry_minutes: int = 5,
    ) -> bool:
        subjects = {
            "registration":   f"[{settings.APP_NAME}] Verify your email — {otp_code}",
            "password_reset": f"[{settings.APP_NAME}] Password reset code",
            "email_change":   f"[{settings.APP_NAME}] Confirm email change",
            "2fa":            f"[{settings.APP_NAME}] Two-factor auth code",
        }
        subject = subjects.get(purpose, f"[{settings.APP_NAME}] Verification code")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.EMAIL_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"]      = recipient_email
        msg["X-Priority"] = "1"

        msg.attach(MIMEText(_plain(otp_code, purpose, expiry_minutes), "plain"))
        msg.attach(MIMEText(_html(otp_code, purpose, expiry_minutes),  "html"))

        if not settings.SMTP_PASSWORD:
            logger.warning("SMTP_PASSWORD not set — skipping real email send. OTP: %s", otp_code)
            return True   # dev mode: pretend it was sent

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as srv:
                srv.ehlo()
                srv.starttls()
                srv.ehlo()
                srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                srv.sendmail(settings.SMTP_USER, recipient_email, msg.as_string())
            logger.info("Email sent → %s (purpose=%s)", recipient_email, purpose)
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP auth failed — check SMTP_USER/SMTP_PASSWORD in .env")
            return False
        except Exception as exc:
            logger.exception("Email send failed: %s", exc)
            return False


email_service = EmailService()
