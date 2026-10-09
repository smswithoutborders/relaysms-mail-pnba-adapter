# RelaySMS Mail PNBA Platform Adapter

Gives [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher) users an email alias tied to their phone number, and sends email from it through [SimpleLogin](https://simplelogin.io). Codes are sent with [Shortmesh Authy](https://github.com/shortmesh/Authy-API). Offline sends, with no linked account, go out from a new random alias. Built with the [RelaySMS Adapter SDK](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk).

## Credentials

Put `credentials.json` in the adapter's config directory. The Publisher keeps it at `data/platforms/config/<adapter id>/credentials.json`.

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
  "RANDOM_ALIAS_PREFIX": "relaysms-",
  "RANDOM_ALIAS_ID_BYTES": 4,
  "SL_BASE_URL": "https://app.simplelogin.io/api",
  "AUTHY_BASE_URL": "https://authy.shortmesh.com",
  "AUTHY_TOKEN": "mt_xxxxx",
  "AUTHY_SENDER": "+237123456789"
}
```

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `SL_PRIMARY_EMAIL` | Yes | - | Your SimpleLogin account email or the mailbox email you want aliases forwarded to. See [SimpleLogin mailboxes](https://app.simplelogin.io/dashboard/mailbox). |
| `SL_PRIMARY_DOMAIN` | Yes | - | The custom domain used for alias generation. Must be verified in SimpleLogin. See [custom domains](https://app.simplelogin.io/dashboard/custom_domain). |
| `SL_API_KEY` | Yes | - | Your SimpleLogin API key. Generate one at [SimpleLogin API Keys](https://app.simplelogin.io/dashboard/api_key). |
| `SMTP_HOST` | Yes | - | SMTP server hostname. Provided by your email provider (e.g. `smtp.gmail.com`, `smtp.protonmail.ch`). |
| `SMTP_PORT` | Yes | - | `465` for implicit TLS, `587` for STARTTLS. |
| `SMTP_USERNAME` | Yes | - | SMTP login username, usually your email address. |
| `SMTP_PASSWORD` | Yes | - | SMTP login password or app password. See your provider's SMTP docs (e.g. [Gmail](https://support.google.com/mail/answer/185833), [Proton](https://proton.me/support/smtp-submission)). |
| `SMTP_USE_TLS` | No | `true` | `true` for port 465 (SMTP_SSL), `false` for port 587 (STARTTLS). |
| `ALIAS_PREFIX` | No | `""` | Static prefix prepended to phone-bound authenticated aliases. |
| `ALIAS_SUFFIX` | No | `""` | Static suffix appended to phone-bound authenticated aliases. |
| `RANDOM_ALIAS_PREFIX` | No | `"relaysms-"` | Prefix string applied to unauthenticated/pooled fallback aliases to comply with anti-spam heuristics. |
| `RANDOM_ALIAS_ID_BYTES` | No | `4` | Byte-entropy count transformed into a hexadecimal suffix appended to random pool extensions (e.g., 4 bytes yields 8 characters). |
| `RANDOM_ALIAS_DB_FILENAME` | No | `"random_aliases.sqlite3"` | SQLite file in the adapter's state directory that tracks random alias prefixes. |
| `SL_BASE_URL` | No | `https://app.simplelogin.io/api` | SimpleLogin API base URL. Override for self-hosted instances. |
| `AUTHY_BASE_URL` | No | `https://authy.shortmesh.com` | Shortmesh Authy API base URL. Override for self-hosted instances. |
| `AUTHY_TOKEN` | No | - | Matrix Bearer token for authenticating with Authy. See [Shortmesh Authy setup](https://github.com/shortmesh/Authy-API#authentication). |
| `AUTHY_SENDER` | No | - | Phone number of the device to send OTPs from. Must be registered with the Authy instance. |

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
