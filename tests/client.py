# SPDX-License-Identifier: GPL-3.0-only

import cmd
import json


class MailAdapterClient(cmd.Cmd):
    intro = "RelaySMS-Mail test client. Type 'help' for commands."
    prompt = "mail> "

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
        """send_message <phone_number> <recipient> <subject> <message>"""
        args = line.split(maxsplit=3)
        if len(args) != 4:
            print("Usage: send_message <phone_number> <recipient> <subject> <message>")
            return
        phone, recipient, subject, message = args
        try:
            result = self.adapter.send_message(
                phone, recipient, message, subject=subject
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
