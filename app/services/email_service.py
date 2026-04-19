import os
import requests

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "")
APP_NAME = os.getenv("APP_NAME", "AutoGrade")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://autograde.toshankanwar.in")


def _validate_brevo_config() -> bool:
    return all([BREVO_API_KEY, EMAIL_FROM, EMAIL_FROM_NAME])


def send_welcome_email(to_email: str, user_name: str = "there") -> bool:
    """
    Sends welcome email via Brevo HTTP API.
    Returns True if sent successfully, else False.
    """
    if not _validate_brevo_config():
        print("[email] Brevo config missing. Skipping email send.")
        return False

    subject = f"Welcome to {APP_NAME} 🚀"

    # SAME UI TEMPLATE (unchanged)
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

    payload = {
        "sender": {
            "email": EMAIL_FROM,
            "name": EMAIL_FROM_NAME
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html
    }

    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    try:
        res = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=20)
        if res.status_code in (200, 201, 202):
            print(f"[email] Welcome email sent to {to_email}")
            return True
        print(f"[email] Brevo send failed: {res.status_code} | {res.text}")
        return False
    except Exception as e:
        print(f"[email] Failed to send welcome email to {to_email}: {e}")
        return False