import base64
import os
import time
import uuid

import requests
import yaml

from crypto import (
    build_request, decode_response,
    make_session_id, next_session_id,
    udid_to_raw,
)

BASE_URL = "https://api.games.umamusume.com/umamusume/"
UNITY_VERSION = "2022.3.62f2"
APP_VERSION = "1.20.14"
RES_VERSION = "10004900"


class UmaClient:
    def __init__(self, cfg):
        self.viewer_id = cfg.get("viewer_id", 0)
        self.udid_str = cfg.get("udid", "")
        self.auth_key_hex = cfg.get("auth_key", "")
        self.steam_id = str(cfg.get("steam_id", ""))
        self.steam_ticket = cfg.get("steam_session_ticket", "")
        self.device_id = cfg.get("device_id", "")
        self.device_name = cfg.get("device_name", "System Product Name")
        self.graphics_device = cfg.get("graphics_device_name", "NVIDIA GeForce GTX 1060")
        self.ip_address = cfg.get("ip_address", "127.0.0.1")
        self.platform_os = cfg.get("platform_os_version", "Windows 10  (10.0.19045) 64bit")
        self.locale = cfg.get("locale", "JPN")
        self.res_ver = RES_VERSION
        self.session_id = bytes(16)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "UnityPlayer/" + UNITY_VERSION + " (UnityWebRequest/1.0, libcurl/8.10.1-DEV)",
            "Content-Type": "application/x-msgpack",
            "Accept": "*/*",
            "X-Unity-Version": UNITY_VERSION,
        })
        if not self.udid_str:
            self.udid_str = str(uuid.uuid4())
        if not self.device_id:
            self.device_id = uuid.uuid4().hex

    def auth_key_bytes(self):
        if not self.auth_key_hex:
            return b""
        return bytes.fromhex(self.auth_key_hex)

    def regen_session_id(self):
        self.session_id = make_session_id(self.viewer_id, self.udid_str)

    def common_fields(self):
        return {
            "carrier": "",
            "device": 4,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "dmm_onetime_token": None,
            "dmm_viewer_id": None,
            "graphics_device_name": self.graphics_device,
            "ip_address": self.ip_address,
            "keychain": 0,
            "locale": self.locale,
            "platform_os_version": self.platform_os,
            "button_info": "",
            "viewer_id": self.viewer_id,
            "steam_id": self.steam_id,
            "steam_session_ticket": self.steam_ticket,
        }

    def request(self, endpoint, extra_fields=None):
        payload = {}
        if extra_fields:
            payload.update(extra_fields)
        payload.update(self.common_fields())
        body = build_request(
            self.session_id,
            udid_to_raw(self.udid_str),
            self.auth_key_bytes(),
            payload,
            self.udid_str,
        )
        url = BASE_URL + endpoint
        headers = {
            "SID": self.session_id.hex(),
            "Device": "4",
            "ViewerID": str(self.viewer_id),
            "APP-VER": APP_VERSION,
            "RES-VER": self.res_ver,
        }
        resp = self.session.post(url, data=body, headers=headers)
        resp_text = resp.text.strip()
        result = decode_response(resp_text, self.udid_str)
        data_headers = result.get("data_headers", {})
        sid = data_headers.get("sid", "")
        if sid:
            self.session_id = next_session_id(sid)
        result_code = data_headers.get("result_code", 0)
        if result_code != 1:
            raise Exception("API error on " + endpoint + ": result_code=" + str(result_code))
        return result

    def signup(self):
        self.regen_session_id()
        self.request("tool/pre_signup", {})
        time.sleep(1)

        self.regen_session_id()
        result = self.request("tool/signup", {
            "error_code": 0,
            "error_message": "",
            "attestation_type": 0,
            "optin_user_birth": 199801,
            "dma_state": 0,
            "country": "Canada",
            "credential": "",
        })
        data = result.get("data", {})
        new_viewer_id = data.get("viewer_id", 0)
        auth_key_b64 = data.get("auth_key", "")
        if new_viewer_id:
            self.viewer_id = new_viewer_id
        if auth_key_b64:
            auth_key_raw = base64.b64decode(auth_key_b64)
            self.auth_key_hex = auth_key_raw.hex()
        return result

    def start_session(self):
        self.regen_session_id()
        result = self.request("tool/start_session", {
            "attestation_type": 0,
            "device_token": None,
        })
        data = result.get("data", {})
        if data:
            self.res_ver = data.get("resource_version", self.res_ver)
        return result

    def load_index(self):
        return self.request("load/index", {})

    def read_info(self):
        return self.request("read_info/index", {
            "add_home_story_data_array": [],
            "add_short_episode_data_array": [],
            "add_home_poster_data_array": [],
            "add_tutorial_guide_data_array": [],
            "add_released_episode_data_array": [],
        })

    def login(self):
        need_signup = (self.viewer_id == 0 or not self.auth_key_hex)
        if need_signup:
            self.signup()

        self.start_session()
        self.load_index()
        time.sleep(1)
        self.read_info()
        return True

    def save_config(self, cfg_path=None):
        if cfg_path is None:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}
        cfg["viewer_id"] = self.viewer_id
        cfg["udid"] = self.udid_str
        cfg["auth_key"] = self.auth_key_hex
        cfg["steam_id"] = self.steam_id
        cfg["steam_session_ticket"] = self.steam_ticket
        cfg["device_id"] = self.device_id
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False)
