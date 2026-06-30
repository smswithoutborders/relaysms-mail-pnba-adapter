# RelaySMS-Mail Platform Adapter

This adapter provides a pluggable implementation for integrating email as a messaging platform via [SimpleLogin](https://simplelogin.io). It is designed to work with [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher), enabling users to send and receive emails through automatically provisioned aliases, with OTP-based authentication handled by [Shortmesh Authy](https://github.com/shortmesh/Authy-API).

## Requirements

- **Python**: Version >= [3.10](https://www.python.org/downloads/)
- **Python Virtual Environments**: [Documentation](https://docs.python.org/3/tutorial/venv.html)
- **libmagic**: For MIME type detection from attachment bytes

## Dependencies

### On Ubuntu

```bash
sudo apt install build-essential python3-dev libmagic1
```

## Installation

1. **Create a virtual environment:**

   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment:**

   ```bash
   . venv/bin/activate
   ```

3. **Install the required Python packages:**

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Set the `credentials.json` path in `manifest.ini`:

```ini
[credentials]
path = ./credentials.json
```

**Sample `credentials.json`**

```json
{
  "SL_PRIMARY_EMAIL": "you@example.com",
  "SL_PRIMARY_DOMAIN": "example.com",
  "SL_API_KEY": "your-simplelogin-api-key",
  "SMTP_HOST": "smtp.example.com",
  "SMTP_PORT": 465,
  "SMTP_USERNAME": "you@example.com",
  "SMTP_PASSWORD": "your-smtp-password",
  "SMTP_USE_TLS": true,
  "ALIAS_PREFIX": "",
  "ALIAS_SUFFIX": "",
  "SL_BASE_URL": "https://app.simplelogin.io/api",
  "AUTHY_BASE_URL": "https://authy.shortmesh.com",
  "AUTHY_TOKEN": "mt_xxxxx",
  "AUTHY_SENDER": "+237123456789"
}
```

**Field reference**

| Field | Required | Default | Description |
|---|---|---|---|
| `SL_PRIMARY_EMAIL` | Yes | - | Your SimpleLogin account email or the mailbox email you want aliases forwarded to. See [SimpleLogin mailboxes](https://app.simplelogin.io/dashboard/mailbox). |
| `SL_PRIMARY_DOMAIN` | Yes | - | The custom domain used for alias generation. Must be verified in SimpleLogin. See [custom domains](https://app.simplelogin.io/dashboard/custom_domain). |
| `SL_API_KEY` | Yes | - | Your SimpleLogin API key. Generate one at [SimpleLogin API Keys](https://app.simplelogin.io/dashboard/api_key). |
| `SMTP_HOST` | Yes | - | SMTP server hostname. Provided by your email provider (e.g. `smtp.gmail.com`, `smtp.protonmail.ch`). |
| `SMTP_PORT` | Yes | - | `465` for implicit TLS, `587` for STARTTLS. |
| `SMTP_USERNAME` | Yes | - | SMTP login username, usually your email address. |
| `SMTP_PASSWORD` | Yes | - | SMTP login password or app password. See your provider's SMTP docs (e.g. [Gmail](https://support.google.com/mail/answer/185833), [Proton](https://proton.me/support/smtp-submission)). |
| `SMTP_USE_TLS` | No | `true` | `true` for port 465 (SMTP_SSL), `false` for port 587 (STARTTLS). |
| `ALIAS_PREFIX` | No | `""` | Static prefix prepended to all generated aliases. |
| `ALIAS_SUFFIX` | No | `""` | Static suffix appended to all generated aliases. |
| `SL_BASE_URL` | No | `https://app.simplelogin.io/api` | SimpleLogin API base URL. Override for self-hosted instances. |
| `AUTHY_BASE_URL` | No | `https://authy.shortmesh.com` | Shortmesh Authy API base URL. Override for self-hosted instances. |
| `AUTHY_TOKEN` | No | - | Matrix Bearer token for authenticating with Authy. See [Shortmesh Authy setup](https://github.com/shortmesh/Authy-API#authentication). |
| `AUTHY_SENDER` | No | - | Phone number of the device to send OTPs from. Must be registered with the Authy instance. |

## Testing

Run the interactive test client:

```bash
python -m tests.client
```

### Available Commands

| Command | Arguments | Description |
|---|---|---|
| `send_code` | `<phone_number> <channel>` | Send an OTP to a phone number via the specified platform |
| `verify` | `<phone_number> <code> <channel>` | Verify an OTP and provision an alias |
| `send_message` | `<phone_number> <recipient> <subject> <message>` | Send an email via the provisioned alias |
| `invalidate` | `<phone_number>` | Disable the alias for a phone number |
| `help` | `[command]` | Show available commands or detail for a specific one |
| `quit` | - | Exit the client |

### Example Session

```
relaysms-mail> send_code +237123456780 wa
{
  "success": true,
  "message": "Authorization code sent."
}

relaysms-mail> verify +237123456780 123456 wa
{
  "userinfo": {
    "account_identifier": "+237123456780",
    "name": "237123456780@example.com"
  }
}

relaysms-mail> send_message +237123456780 recipient@example.com "Hello from RelaySMS" "This is a test email."
Sent: True

relaysms-mail> send_message +237123456780 recipient@example.com "Report" "Please find the report attached." ~/documents/report.pdf

relaysms-mail> invalidate +237123456780
Invalidated: True

relaysms-mail> quit
```
