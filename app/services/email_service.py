import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SMTP_HOST = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
APP_NAME = os.getenv("APP_NAME", "AutoGrade")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://autograde.toshankanwar.in")


def _validate_smtp_config() -> bool:
    return all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM])


def send_welcome_email(to_email: str, user_name: str = "there") -> bool:
    """
    Sends welcome email via Brevo SMTP.
    Returns True if sent successfully, else False.
    """
    if not _validate_smtp_config():
        print("[email] SMTP config missing. Skipping email send.")
        return False

    subject = f"Welcome to {APP_NAME} 🚀"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Welcome to {APP_NAME}</title>
      </head>
      <body style="margin:0; padding:0; background:#f3f4f6; font-family:Arial,Helvetica,sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f4f6; padding:32px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px; background:#ffffff; border-radius:18px; overflow:hidden; border:1px solid #e5e7eb; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
                
                <!-- Header -->
                <tr>
                  <td style="padding:0; background:linear-gradient(135deg,#0ea5e9 0%,#6366f1 50%,#8b5cf6 100%);">
                    <table width="100%" role="presentation" cellspacing="0" cellpadding="0">
                      <tr>
                        <td style="padding:28px 28px 22px;">
                          <p style="margin:0; color:#e0f2fe; font-size:12px; letter-spacing:1.2px; text-transform:uppercase;">
                            Welcome aboard
                          </p>
                          <h1 style="margin:8px 0 6px; color:#ffffff; font-size:28px; line-height:1.2;">
                            {APP_NAME}
                          </h1>
                          <p style="margin:0; color:#eef2ff; font-size:14px;">
                            Your account is live. Let’s do something amazing ✨
                          </p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- Body -->
                <tr>
                  <td style="padding:30px 28px 10px;">
                    <h2 style="margin:0 0 10px; font-size:22px; color:#111827;">
                      Hi {user_name} 👋
                    </h2>
                    <p style="margin:0 0 14px; font-size:15px; line-height:1.7; color:#374151;">
                      Welcome to <b>{APP_NAME}</b>! Your account has been created successfully.
                    </p>
                    <p style="margin:0 0 20px; font-size:15px; line-height:1.7; color:#374151;">
                      You can now sign in, upload your work, and start using all core features.
                    </p>

                    <!-- CTA -->
                    <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 22px;">
                      <tr>
                        <td align="center" bgcolor="#4f46e5" style="border-radius:10px;">
                          <a href="{FRONTEND_URL}" target="_blank"
                             style="display:inline-block; padding:12px 22px; font-size:14px; font-weight:700; color:#ffffff; text-decoration:none;">
                            🚀 Get Started
                          </a>
                        </td>
                      </tr>
                    </table>

                    <!-- Highlights -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:4px 0 22px; border:1px solid #e5e7eb; border-radius:12px;">
                      <tr>
                        <td style="padding:14px 14px 4px; font-size:14px; color:#111827; font-weight:700;">
                          What you can do next:
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:0 14px 14px; font-size:14px; color:#4b5563; line-height:1.8;">
                          ✅ Upload answer sheets<br/>
                          ✅ Check OCR extraction accuracy<br/>
                          ✅ Review scoring insights quickly
                        </td>
                      </tr>
                    </table>

                    <p style="margin:0 0 22px; font-size:12px; color:#6b7280; line-height:1.7;">
                      If you did not create this account, you can safely ignore this email.
                    </p>
                  </td>
                </tr>

                <!-- Footer -->
                <tr>
                  <td style="padding:14px 28px; background:#f9fafb; border-top:1px solid #e5e7eb;">
                    <p style="margin:0; font-size:12px; color:#6b7280;">
                      © {APP_NAME} • Built with care for better evaluation workflows.
                    </p>
                  </td>
                </tr>

              </table>

              <p style="margin:14px 0 0; font-size:11px; color:#9ca3af;">
                This is an automated email, please do not reply.
              </p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
        print(f"[email] Welcome email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[email] Failed to send welcome email to {to_email}: {e}")
        return False