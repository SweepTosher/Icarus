import json
import os
import subprocess
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TICKET_SCRIPT = os.path.join(SCRIPT_DIR, "ticket_gen.js")


def get_steam_ticket(username, password, code=""):
    cmd = ["node", TICKET_SCRIPT, "--username", username, "--password", password]
    if code:
        cmd.extend(["--code", code])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=SCRIPT_DIR,
    )
    if proc.returncode == 2:
        code = input("Enter Steam 2FA code: ").strip()
        return get_steam_ticket(username, password, code)
    stdout = proc.stdout.strip()
    if not stdout:
        raise Exception("no ticket data received")
    line = stdout.split("\n")[-1]
    data = json.loads(line)
    return data["steam_id"], data["session_ticket"]
