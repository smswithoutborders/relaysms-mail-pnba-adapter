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
| `SL_PRIMARY_EMAIL` | Yes | - | Mailbox email address in SimpleLogin |
| `SL_PRIMARY_DOMAIN` | Yes | - | Domain used for alias generation |
| `SL_API_KEY` | Yes | - | SimpleLogin API key |
| `SMTP_HOST` | Yes | - | SMTP server hostname |
| `SMTP_PORT` | Yes | - | `465` for TLS, `587` for STARTTLS |
| `SMTP_USERNAME` | Yes | - | SMTP login username |
| `SMTP_PASSWORD` | Yes | - | SMTP login password |
| `SMTP_USE_TLS` | No | `true` | Use implicit TLS (port 465) |
| `ALIAS_PREFIX` | No | `""` | Prefix prepended to generated aliases |
| `ALIAS_SUFFIX` | No | `""` | Suffix appended to generated aliases |
| `SL_BASE_URL` | No | `https://app.simplelogin.io/api` | SimpleLogin API base URL |
| `AUTHY_BASE_URL` | No | `https://authy.shortmesh.com` | Shortmesh Authy API base URL |
| `AUTHY_TOKEN` | No | - | Matrix Bearer token for Authy authentication |
| `AUTHY_SENDER` | No | - | Device number to send OTPs from |

## Testing

Install dev dependencies:

```bash
pip install -r requirements.txt
```

Run the test client:

```bash
python -m tests.client
```

### Available Commands

| Command | Arguments | Description |
|---|---|---|
| `send_code` | `<phone_number> <channel>` | Send an OTP to a phone number via the specified platform |
| `verify` | `<phone_number> <code> <channel>` | Verify an OTP and provision an alias |
| `send_message` | `<phone_number> <recipient> <subject> <message>` | Send an email via the provisioned alias |
| `invalidate` | `<phone_number>` | Delete the alias for a phone number |
| `help` | `[command]` | Show available commands or detail for a specific one |
| `quit` | - | Exit the client |

### Example Session

```
mail> send_code +237123456780 wa
{}

mail> verify +237123456780 123456 wa
{
  "userinfo": {
    "account_identifier": "+237123456780",
    "name": "237123456780@example.com"
  }
}

mail> send_message +237123456780 recipient@example.com "Hello from RelaySMS" "This is a test email."
Sent: True

mail> invalidate +237123456780
Invalidated: True

mail> quit
```
