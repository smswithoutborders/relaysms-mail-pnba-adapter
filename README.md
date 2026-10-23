# RelaySMS Mail PNBA Platform Adapter

Gives [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher) users an email alias tied to their phone number, and sends email from it through [SimpleLogin](https://simplelogin.io). Codes are sent with [Shortmesh Authy](https://github.com/shortmesh/Authy-API). Offline sends, with no linked account, go out from a new random alias. Built with the [RelaySMS Adapter SDK](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk).

## Settings

Each setting is described in [adapter.toml](adapter.toml). The required ones come from [SimpleLogin](https://app.simplelogin.io/dashboard/api_key), with a [verified domain](https://app.simplelogin.io/dashboard/custom_domain), and your SMTP provider. Codes are sent with [Shortmesh Authy](https://github.com/shortmesh/Authy-API#authentication); set `authy_base_url`, `authy_token` and `authy_sender` to send from your own Authy. On a Publisher, set them up as its [RelaySMS Mail guide](https://github.com/smswithoutborders/RelaySMS-Publisher/blob/main/docs/platforms/relaysms-mail.md) describes.

## Develop

```bash
python3 -m venv venv
venv/bin/pip install -e '.[dev]'
venv/bin/pytest
```

To try it, use the [`relaysms-adapter`](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk#try-it) console. `--channel` is the Authy platform the code goes out on, such as `wa`.

```bash
venv/bin/relaysms-adapter config set sl_primary_email=you@example.com \
  sl_primary_domain=example.com smtp_host=smtp.example.com smtp_port=465 \
  smtp_username=you@example.com sl_api_key smtp_password
venv/bin/relaysms-adapter link --phone +237600000000 --channel wa
venv/bin/relaysms-adapter send --to you@example.com --subject Hi --body hello
venv/bin/relaysms-adapter send --offline --to you@example.com --subject Hi --body hello
```
