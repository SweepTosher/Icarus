import os
import sys
import time
import yaml

from client import UmaClient
from steam_auth import get_steam_ticket

TARGET_TYPES = {1: "Spd", 2: "Sta", 3: "Pow", 4: "Gut", 5: "Wiz", 10: "Vit", 30: "SkPt"}

TRAINING_COMMANDS = [
    (101, "Speed",   "spd"),
    (105, "Stamina", "sta"),
    (102, "Power",   "pow"),
    (103, "Guts",    "guts"),
    (106, "Wisdom",  "wit"),
]

CMD_NAMES    = {cid: name for cid, name, _    in TRAINING_COMMANDS}
CMD_SHORT    = {abbr: cid for cid, _,    abbr in TRAINING_COMMANDS}
TRAINING_IDS = [cid        for cid, _,    _    in TRAINING_COMMANDS]


def load_config():
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if not os.path.exists(cfg_path):
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def do_login(client, cfg):
    username = cfg.get("steam_username", "")
    password = cfg.get("steam_password", "")
    if not username:
        username = input("Steam username: ").strip()
    if not password:
        password = input("Steam password: ").strip()
    steam_id, ticket = get_steam_ticket(username, password)
    client.steam_id = steam_id
    client.steam_ticket = ticket
    client.login()
    client.save_config()
    print("Logged in!")


def show_stats(ci):
    if not ci:
        print("No career data")
        return
    print("  Turn " + str(ci.get("turn", "?"))
          + "  Motivation:" + str(ci.get("motivation", 0))
          + "  Energy:" + str(ci.get("vital", 0)) + "/" + str(ci.get("max_vital", 100))
          + "  Fans:" + str(ci.get("fans", 0))
          + "  SkillPt:" + str(ci.get("skill_point", 0)))
    print("  Spd:" + str(ci.get("speed", 0)).rjust(4)
          + "  Sta:" + str(ci.get("stamina", 0)).rjust(4)
          + "  Pow:" + str(ci.get("power", 0)).rjust(4)
          + "  Gut:" + str(ci.get("guts", 0)).rjust(4)
          + "  Wit:" + str(ci.get("wiz", 0)).rjust(4))


def build_bond_map(ci):
    bonds = {}
    for ev in ci.get("evaluation_info_array", []):
        tid = ev.get("target_id", 0)
        bonds[tid] = ev.get("evaluation", 0)
    return bonds


def build_team_command_map(team_data_set):
    tcm = {}
    if not team_data_set:
        return tcm
    for cmd in team_data_set.get("command_info_array", []):
        cid = cmd.get("command_id", 0)
        tcm[cid] = cmd
    return tcm


def partner_label(pid, bonds):
    bond = bonds.get(pid, -1)
    tag = ("S" if 1 <= pid <= 6 else "T") + str(pid)
    if bond >= 0:
        tag += "(" + str(bond) + ")"
    return tag


def format_stat_changes(params):
    parts = []
    for p in params:
        tt = p.get("target_type", 0)
        val = p.get("value", 0)
        name = TARGET_TYPES.get(tt, "?" + str(tt))
        sign = "+" if val >= 0 else ""
        parts.append(name + sign + str(val))
    return "  ".join(parts)


def show_training_options(data, chara_info):
    home_info = data.get("home_info", {})
    commands = home_info.get("command_info_array", [])
    team_data_set = data.get("team_data_set")
    team_cmd_map = build_team_command_map(team_data_set)
    bonds = build_bond_map(chara_info) if chara_info else {}

    training_cmds = {
        cmd.get("command_id"): cmd
        for cmd in commands
        if cmd.get("command_type") == 1
    }

    print("")
    print("--- Training ---")
    for cid in TRAINING_IDS:
        cmd = training_cmds.get(cid)
        if not cmd:
            continue
        name    = CMD_NAMES[cid]
        params   = cmd.get("params_inc_dec_info_array", [])
        partners = cmd.get("training_partner_array", [])
        fail     = cmd.get("failure_rate", 0)
        tips     = cmd.get("tips_event_partner_array", [])
        enabled  = cmd.get("is_enable", 0)

        tcmd  = team_cmd_map.get(cid, {})
        guide = tcmd.get("guide_event_partner_array", [])
        soul  = tcmd.get("soul_event_partner_array", [])

        status      = "" if enabled else " [LOCKED]"
        partner_str = ", ".join(partner_label(p, bonds) for p in partners) if partners else "-"

        print("  " + name.ljust(7) + " " + format_stat_changes(params)
              + "  Fail:" + str(fail) + "%" + status)

        detail = "    Partners: " + partner_str
        if tips:
            detail += "  Hint:"  + ",".join(str(t) for t in tips)
        if guide:
            detail += "  Guide:" + ",".join(str(g) for g in guide)
        if soul:
            detail += "  Soul:"  + ",".join(str(s) for s in soul)
        print(detail)

    print("")


def show_events(data):
    events = data.get("unchecked_event_array", [])
    if not events:
        return False
    print("--- Pending Events ---")
    for ev in events:
        eid     = ev.get("event_id", 0)
        choices = ev.get("event_contents_info", {}).get("choice_array", [])
        print("  Event " + str(eid) + "  choices=" + str(len(choices)))
        for i, ch in enumerate(choices):
            print("    [" + str(ch.get("select_index", i)) + "]")
    print("")
    return True


def show_team_info(team_data_set, bonds):
    if not team_data_set:
        return
    tinfo = team_data_set.get("team_info", {})
    if not tinfo:
        return
    print("--- Team ---")
    print("  Rank:" + str(tinfo.get("team_rank", 0))
          + "  Power:" + str(tinfo.get("team_power", 0)))
    for m in tinfo.get("team_chara_info_array", []):
        pid = m.get("training_partner_id", 0)
        print("    " + partner_label(pid, bonds).ljust(12)
              + " Spd:" + str(m.get("speed", 0)).rjust(4)
              + " Sta:" + str(m.get("stamina", 0)).rjust(4)
              + " Pow:" + str(m.get("power", 0)).rjust(4)
              + " Gut:" + str(m.get("guts", 0)).rjust(4)
              + " Wit:" + str(m.get("wiz", 0)).rjust(4)
              + " Rank:" + str(m.get("rank_score", 0)).rjust(5))
    print("")


def show_full_state(data, chara_info):
    show_stats(chara_info)
    show_events(data)
    show_training_options(data, chara_info)
    bonds = build_bond_map(chara_info) if chara_info else {}
    show_team_info(data.get("team_data_set"), bonds)


def resolve_events(client, data, chara_info, turn, auto_choice=None):
    events = data.get("unchecked_event_array", [])
    while events:
        ev      = events[0]
        eid     = ev.get("event_id", 0)
        choices = ev.get("event_contents_info", {}).get("choice_array", [])

        if auto_choice is not None:
            cn = auto_choice
        elif len(choices) <= 1:
            cn = choices[0].get("select_index", 1) if choices else 1
        else:
            print("  Event " + str(eid) + " has " + str(len(choices)) + " choices:")
            for ch in choices:
                print("    [" + str(ch.get("select_index", 0)) + "]")
            try:
                cn = int(input("  Pick choice: ").strip())
            except ValueError:
                cn = 1

        time.sleep(0.5)
        r    = client.request("single_mode_team/check_event", {
            "event_id":      eid,
            "chara_id":      ev.get("chara_id", 0),
            "choice_number": cn,
            "current_turn":  turn,
        })
        data = r.get("data", {})
        ci   = data.get("chara_info")
        if ci:
            chara_info = ci
            turn       = ci.get("turn", turn)
        events = data.get("unchecked_event_array", [])

    return data, chara_info, turn


def main():
    cfg    = load_config()
    client = UmaClient(cfg)
    chara_info = None
    last_data  = None
    turn   = 0
    energy = 0

    short_list = "/".join(abbr for _, _, abbr in TRAINING_COMMANDS)
    print("Commands: login | load | train <" + short_list + ">")

    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not cmd:
            continue

        parts  = cmd.split(None, 1)
        action = parts[0].lower()
        arg    = parts[1].strip().lower() if len(parts) > 1 else ""

        if action == "login":
            try:
                do_login(client, cfg)
            except Exception as e:
                print("Login failed: " + str(e))

        elif action == "load":
            try:
                result     = client.request("single_mode_team/load", {})
                data       = result.get("data", {})
                chara_info = data.get("chara_info")
                if not chara_info:
                    print("No active career. Start one in game first.")
                    continue
                turn   = chara_info.get("turn", 0)
                energy = chara_info.get("vital", 0)
                print("Career loaded!")

                if data.get("unchecked_event_array"):
                    data, chara_info, turn = resolve_events(client, data, chara_info, turn)
                    energy = chara_info.get("vital", energy)

                last_data = data
                show_full_state(data, chara_info)
            except Exception as e:
                if "205" in str(e):
                    print("No active career (205). Start one in game first.")
                else:
                    print("Load error: " + str(e))

        elif action == "train":
            if not arg or arg not in CMD_SHORT:
                print("Usage: train <" + short_list + ">")
                continue
            program = CMD_SHORT[arg]
            name    = CMD_NAMES[program]
            try:
                result = client.request("single_mode_team/exec_command", {
                    "command_type":     1,
                    "command_id":       program,
                    "command_group_id": 0,
                    "select_id":        0,
                    "current_turn":     turn,
                    "current_vital":    energy,
                })
                data = result.get("data", {})
                ci   = data.get("chara_info")
                if ci:
                    chara_info = ci
                    turn       = ci.get("turn", turn)
                    energy     = ci.get("vital", energy)

                if data.get("unchecked_event_array"):
                    data, chara_info, turn = resolve_events(client, data, chara_info, turn)
                    energy = chara_info.get("vital", energy)

                last_data = data
                print("Trained " + name + "!")
                show_full_state(data, chara_info)
            except Exception as e:
                print("Train error: " + str(e))

        else:
            print("Unknown comman")

if __name__ == "__main__":
    main()