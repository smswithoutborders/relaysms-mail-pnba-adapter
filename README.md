# RelaySMS Mail PNBA Platform Adapter

Gives [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher) users an email alias tied to their phone number, and sends email from it through [SimpleLogin](https://simplelogin.io). Codes are sent with [Shortmesh Authy](https://github.com/shortmesh/Authy-API). Offline sends, with no linked account, go out from a new random alias. Built with the [RelaySMS Adapter SDK](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk).

## Credentials

Put `credentials.json` in the adapter's config directory. The Publisher keeps it at `data/platforms/config/<adapter id>/credentials.json`. Keys can be in lowercase or uppercase, such as `smtp_host` or `SMTP_HOST`.

```json
{
  "sl_primary_email": "you@example.com",
  "sl_primary_domain": "example.com",
  "sl_api_key": "your-simplelogin-api-key",
  "smtp_host": "smtp.example.com",
  "smtp_port": 465,
  "smtp_username": "you@example.com",
  "smtp_password": "your-smtp-password",
  "smtp_use_tls": true,
  "alias_prefix": "",
  "alias_suffix": "",
  "random_alias_prefix": "relaysms-",
  "random_alias_id_bytes": 4,
  "sl_base_url": "https://app.simplelogin.io/api",
  "authy_base_url": "https://authy.shortmesh.com",
  "authy_token": "mt_xxxxx",
  "authy_sender": "+237123456789"
}
```

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `sl_primary_email` | Yes | - | Your SimpleLogin account email or the mailbox email you want aliases forwarded to. See [SimpleLogin mailboxes](https://app.simplelogin.io/dashboard/mailbox). |
| `sl_primary_domain` | Yes | - | The custom domain used for alias generation. Must be verified in SimpleLogin. See [custom domains](https://app.simplelogin.io/dashboard/custom_domain). |
| `sl_api_key` | Yes | - | Your SimpleLogin API key. Generate one at [SimpleLogin API Keys](https://app.simplelogin.io/dashboard/api_key). |
| `smtp_host` | Yes | - | SMTP server hostname. Provided by your email provider (e.g. `smtp.gmail.com`, `smtp.protonmail.ch`). |
| `smtp_port` | Yes | - | `465` for implicit TLS, `587` for STARTTLS. |
| `smtp_username` | Yes | - | SMTP login username, usually your email address. |
| `smtp_password` | Yes | - | SMTP login password or app password. See your provider's SMTP docs (e.g. [Gmail](https://support.google.com/mail/answer/185833), [Proton](https://proton.me/support/smtp-submission)). |
| `smtp_use_tls` | No | `true` | `true` for port 465 (SMTP over SSL), `false` for port 587 (STARTTLS). |
| `alias_prefix` | No | `""` | Static prefix prepended to phone-bound authenticated aliases. |
| `alias_suffix` | No | `""` | Static suffix appended to phone-bound authenticated aliases. |
| `random_alias_prefix` | No | `"relaysms-"` | Prefix string applied to unauthenticated/pooled fallback aliases to comply with anti-spam heuristics. |
| `random_alias_id_bytes` | No | `4` | Byte-entropy count transformed into a hexadecimal suffix appended to random pool extensions (e.g., 4 bytes yields 8 characters). |
| `random_alias_db_filename` | No | `"random_aliases.sqlite3"` | SQLite file in the adapter's state directory that tracks random alias prefixes. |
| `sl_base_url` | No | `https://app.simplelogin.io/api` | SimpleLogin API base URL. Override for self-hosted instances. |
| `authy_base_url` | No | `https://authy.shortmesh.com` | Shortmesh Authy API base URL. Override for self-hosted instances. |
| `authy_token` | No | - | Matrix Bearer token for authenticating with Authy. See [Shortmesh Authy setup](https://github.com/shortmesh/Authy-API#authentication). |
| `authy_sender` | No | - | Phone number of the device to send OTPs from. Must be registered with the Authy instance. |

## Develop

```bash
python3 -m venv venv
venv/bin/pip install -e '.[dev]'
venv/bin/pytest
```

To try it, put `credentials.json` in `.relaysms/config/` and use the [`relaysms-adapter`](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk#try-it) console. `--channel` is the Authy platform the code goes out on, such as `wa`.

```bash
venv/bin/relaysms-adapter link --phone +237600000000 --channel wa
venv/bin/relaysms-adapter send --to you@example.com --subject Hi --body hello
venv/bin/relaysms-adapter send --offline --to you@example.com --subject Hi --body hello
```
