import base64
import hashlib
import os
import random
import struct

import msgpack
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

SALT = b"co!=Y;(UQCGxJ_n82"

COMMON_HEADER = bytes.fromhex(
    "6b20e2ab6c311330f761d737ce3f3025"
    "750850665eea58b6372f8d2f57501eb3"
    "44bdb7270a9067f5b63cd61f152cfb98"
    "6cbfbf7a"
)


def salted_md5(data):
    h = hashlib.md5()
    h.update(data)
    h.update(SALT)
    return h.digest()


def make_session_id(viewer_id, udid_str):
    raw = str(viewer_id) + udid_str
    return salted_md5(raw.encode("utf-8"))


def next_session_id(sid_string):
    return salted_md5(sid_string.encode("utf-8"))


def gen_key():
    out = bytearray()
    while len(out) < 32:
        num = random.randint(0, 65535)
        hexstr = format(num, "x")
        out.extend(hexstr.encode("ascii"))
    return bytes(out[:32])


def udid_to_iv(udid_str):
    clean = udid_str.replace("-", "").lower()
    return clean[:16].encode("ascii")


def udid_to_raw(udid_str):
    clean = udid_str.replace("-", "").lower()
    return bytes.fromhex(clean)


def build_request(session_id, udid_raw, auth_key_bytes, payload, udid_str):
    key = gen_key()
    packed = msgpack.packb(payload, use_bin_type=True)
    length_prefix = struct.pack("<I", len(packed))
    plaintext = length_prefix + packed
    iv = udid_to_iv(udid_str)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(plaintext, 16))
    body = encrypted + key
    random_bytes = os.urandom(32)
    header = bytearray()
    header.extend(COMMON_HEADER)
    header.extend(session_id)
    header.extend(udid_raw)
    header.extend(random_bytes)
    if auth_key_bytes:
        header.extend(auth_key_bytes)
    header_bytes = bytes(header)
    header_len = struct.pack("<I", len(header_bytes))
    wire = header_len + header_bytes + body
    return base64.b64encode(wire)


def decode_response(response_text, udid_str):
    raw = base64.b64decode(response_text)
    key = raw[-32:]
    ciphertext = raw[:-32]
    iv = udid_to_iv(udid_str)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(ciphertext), 16)
    payload_len = struct.unpack("<I", decrypted[:4])[0]
    payload = decrypted[4:4 + payload_len]
    return msgpack.unpackb(payload, raw=False, strict_map_key=False)
