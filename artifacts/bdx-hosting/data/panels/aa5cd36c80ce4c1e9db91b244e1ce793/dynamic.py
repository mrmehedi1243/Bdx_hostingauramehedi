import asyncio
import aiohttp
import ssl
import uuid
import random
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import json

# ========== PROTOBUF IMPORTS (EXACTLY AS IN RAFIN4.py) ==========
try:
    from Pb2 import MajoRLoGinrEq_pb2   # for request
    from Pb2 import MajoRLoGinrEs_pb2   # for response
except ImportError:
    print("❌ Could not import pb2 modules. Make sure the Pb2 folder is present.")
    exit(1)

RIFATx = "1.123.17"

# ========== Encrypt_Proto (same as RAFIN4.py) ==========
async def Encrypt_Proto(payload: bytes):
    key = b"Yg&tc%DEuh6%Zc^8"
    iv = b"6oyZDr22E3ychjM%"
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(payload, AES.block_size)
    return cipher.encrypt(padded)

# ========== Build MajorLogin Request (same hardcoded device) ==========
async def EncRypTMajoRLoGin(open_id, access_token):
    major_login = MajoRLoGinrEq_pb2.MajorLogin()
    major_login.event_time = str(datetime.now())[:-7]
    major_login.game_name = "free fire"
    major_login.platform_id = 2
    major_login.client_version = RIFATx
    major_login.client_version_code = "2024010012"
    major_login.system_software = "Android OS 11 / API-30 (RQ3A.210805.001)"
    major_login.system_hardware = "Handheld"
    major_login.device_type = "Handheld"
    major_login.telecom_operator = "Verizon"
    major_login.network_operator_a = "Verizon"
    major_login.network_type = "WIFI"
    major_login.network_type_a = "WIFI"
    major_login.screen_width = 1080
    major_login.screen_height = 2400
    major_login.screen_dpi = "440"
    major_login.processor_details = "ARMv8"
    major_login.cpu_type = 2
    major_login.cpu_architecture = "64"
    major_login.memory = 6144
    major_login.gpu_renderer = "Adreno (TM) 650"
    major_login.gpu_version = "OpenGL ES 3.2 V@1.50"
    major_login.graphics_api = "OpenGLES3"
    major_login.unique_device_id = f"Google|{uuid.uuid4()}"
    major_login.client_ip = ""
    major_login.language = "en"
    major_login.open_id = open_id
    major_login.open_id_type = "4"
    major_login.login_open_id_type = 4
    major_login.access_token = access_token
    major_login.login_by = 3
    major_login.platform_sdk_id = 2
    major_login.origin_platform_type = "4"
    major_login.primary_platform_type = "4"

    memory_available = major_login.memory_available
    memory_available.version = 55
    memory_available.hidden_value = 81
    major_login.external_storage_total = 128512
    major_login.external_storage_available = random.randint(38000, 52000)
    major_login.internal_storage_total = 110731
    major_login.internal_storage_available = random.randint(18000, 32000)
    major_login.game_disk_storage_total = 26628
    major_login.game_disk_storage_available = random.randint(18000, 25000)
    major_login.external_sdcard_total_storage = 119234
    major_login.external_sdcard_avail_storage = random.randint(25000, 60000)
    major_login.library_path = "/data/app/~~random/base.apk"
    major_login.library_token = "hash|base.apk"
    major_login.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    major_login.supported_astc_bitset = 16383
    major_login.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWAUOUgsvA1snWlBaO1kFYg=="
    major_login.loading_time = random.randint(9000, 18000)
    major_login.release_channel = "android"
    major_login.channel_type = 3
    major_login.reg_avatar = 1
    major_login.if_push = 1
    major_login.is_vpn = 0
    major_login.android_engine_init_flag = 110009

    string = major_login.SerializeToString()
    return await Encrypt_Proto(string)

# ========== Send MajorLogin Request ==========
async def MajorLogin(payload):
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "RAFIN/1.0 (Linux; Android 13; SM-S918B Build/TP1A.220.624.014)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers, ssl=ssl_context) as response:
            if response.status == 200:
                return await response.read()
            return None

# ========== Decrypt MajorLogin Response ==========
async def DecRypTMajoRLoGin(data):
    proto = MajoRLoGinrEs_pb2.MajorLoginRes()   # <- FIXED: use response proto
    proto.ParseFromString(data)
    return proto

# ========== Get OAuth Token ==========
async def GeNeRaTeAccEss(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    headers = {
        "User-Agent": "RAFIN/1.0 (Linux; Android 13; SM-S918B Build/TP1A.220.624.014)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            if response.status != 200:
                return None, None
            resp_json = await response.json()
            open_id = resp_json.get("open_id")
            access_token = resp_json.get("access_token")
            return open_id, access_token

# ========== Main ==========
async def main(uid, password):
    print(f"[*] Getting access token for UID {uid}...")
    open_id, access_token = await GeNeRaTeAccEss(uid, password)
    if not open_id or not access_token:
        print("❌ Failed to get access token. Check UID/password.")
        return

    print("[*] Building MajorLogin payload...")
    payload = await EncRypTMajoRLoGin(open_id, access_token)

    print("[*] Sending MajorLogin request...")
    response = await MajorLogin(payload)
    if not response:
        print("❌ MajorLogin failed – no response from server.")
        return

    print("[*] Decrypting response...")
    login_data = await DecRypTMajoRLoGin(response)

    if hasattr(login_data, 'token') and login_data.token:
        print("\n✅ SUCCESS!\n")
        print(f"🔑 Key (hex): {login_data.key.hex()}")
        print(f"🔐 IV  (hex): {login_data.iv.hex()}")
        print(f"📛 Account UID: {login_data.account_uid}")
        print(f"🌍 Region: {login_data.region}")
        print(f"🎟️ JWT Token (first 50 chars): {login_data.token[:50]}...")
    else:
        print("❌ Failed to extract key/iv. Possibly invalid credentials or banned account.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python dynamic.py <UID> <password>")
        print("Example: python dynamic.py 123456789 mypassword")
        sys.exit(1)
    uid = sys.argv[1]
    password = sys.argv[2]
    asyncio.run(main(uid, password))