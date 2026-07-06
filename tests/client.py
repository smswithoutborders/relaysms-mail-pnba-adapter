# SPDX-License-Identifier: GPL-3.0-only

import base64
import cmd
import json
import shlex
from pathlib import Path


class MailAdapterClient(cmd.Cmd):
    intro = "RelaySMS-Mail test client. Type help or ? for a list of commands."
    prompt = "relaysms-mail> "

    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter

    def do_send_code(self, line):
        """send_code <phone_number> <channel>"""
        args = line.split()
        if len(args) != 2:
            print("Usage: send_code <phone_number> <channel>")
            return
        phone, channel = args
        try:
            result = self.adapter.send_authorization_code(phone, channel=channel)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error: {e}")

    def do_verify(self, line):
        """verify <phone_number> <code> <channel>"""
        args = line.split()
        if len(args) != 3:
            print("Usage: verify <phone_number> <code> <channel>")
            return
        phone, code, channel = args
        try:
            result = self.adapter.validate_code_and_fetch_user_info(
                phone, code, channel=channel
            )
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error: {e}")

    def do_send_message(self, line):
        """send_message <phone_number_or_none> <recipient> <subject> <message> [file_path]"""
        try:
            args = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}")
            return

        if len(args) < 4:
            print(
                "Usage: send_message <phone_number_or_none> <recipient> <subject> <message> [file_path]\n"
                "Tip: Pass '-' to skip phone lookup and trigger a random alias."
            )
            return

        phone_arg, recipient, subject, message = args[:4]
        file_path_str = args[4] if len(args) == 5 else None
        attachments = []

        phone = None if phone_arg.lower() == "-" else phone_arg

        if file_path_str:
            path = Path(file_path_str).expanduser()
            if not path.is_file():
                print(f"Error: Provided path is not a file or does not exist: {path}")
                return
            try:
                b64_data = base64.b64encode(path.read_bytes()).decode("utf-8")
                attachments.append({"data": b64_data})
            except Exception as e:
                print(f"Error reading attachment: {e}")
                return

        try:
            result = self.adapter.send_message(
                phone_number=phone,
                to_email=recipient,
                message=message,
                subject=subject,
                attachments=attachments,
            )
            print(f"Sent: {result}")
        except Exception as e:
            print(f"Error: {e}")

    def do_invalidate(self, line):
        """invalidate <phone_number>"""
        if not line.strip():
            print("Usage: invalidate <phone_number>")
            return
        try:
            result = self.adapter.invalidate_session(line.strip())
            print(f"Invalidated: {result}")
        except Exception as e:
            print(f"Error: {e}")

    def do_quit(self, _):
        """Exit the client."""
        return True

    do_EOF = do_quit


if __name__ == "__main__":
    from adapter import RelaySMSMailPNBAAdapter

    MailAdapterClient(RelaySMSMailPNBAAdapter()).cmdloop()
