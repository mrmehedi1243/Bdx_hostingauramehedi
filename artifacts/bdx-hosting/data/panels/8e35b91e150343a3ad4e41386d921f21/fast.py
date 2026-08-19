#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MEHEDI GUEST GEN PRO 🔥 - EXTREME FAST
Region: BD (Bangladesh)
Owner: @MEHEDIXAURA
"""

import os, sys, json, time, random, threading, base64, codecs, uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
#  COLORS
# ============================================================
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RED = "\033[91m"
PURPLE = "\033[95m"
WHITE = "\033[97m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

SPINNERS = ["◐", "◓", "◑", "◒"]
COLORS = [CYAN, BLUE, PURPLE, YELLOW, GREEN]

def get_color(i):
    return COLORS[i % len(COLORS)]

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    print(f"""
{BOLD}{PURPLE}
╔═══════════════════════════════════════════════════════════╗
║  ███╗   ███╗███████╗██╗  ██╗███████╗██████╗ ██╗         ║
║  ████╗ ████║██╔════╝██║  ██║██╔════╝██╔══██╗██║         ║
║  ██╔████╔██║█████╗  ███████║█████╗  ██║  ██║██║         ║
║  ██║╚██╔╝██║██╔══╝  ██╔══██║██╔══╝  ██║  ██║██║         ║
║  ██║ ╚═╝ ██║███████╗██║  ██║███████╗██████╔╝███████╗    ║
║  ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝ ╚══════╝    ║
╚═══════════════════════════════════════════════════════════╝
{RESET}
{BOLD}{YELLOW}   🔥 MEHEDI GUEST GEN PRO - EXTREME FAST 🔥{RESET}
{GREEN}   📩 OWNER : @MEHEDIXAURA{RESET}
{BOLD}{GREEN}   ⚡ EXTREME SPEED MODE ACTIVE ⚡{RESET}
""")

# ============================================================
#  SETTINGS
# ============================================================
REGION = "BD"
THREADS = 20
TOTAL_ACCOUNTS = 10
NAME_PREFIX = "MEHEDI"
RETRIES = 1

# ============================================================
#  CRYPTO KEYS
# ============================================================
AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
NICK_XOR_KEY = b'1e5898ccb8dfdd921f9bdea848768b64a201'

# ============================================================
#  NAME GENERATOR
# ============================================================
def generate_hex_password():
    return ''.join(random.choice('0123456789ABCDEF') for _ in range(64))

exp_digits = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'}
def generate_clean_nickname(prefix):
    if not prefix:
        prefix = "MEHEDI"
    num = random.randint(1, 99999)
    suffix = ''.join(exp_digits[d] for d in f"{num:05d}")
    name = f"{prefix[:8]}{suffix}"
    return name[:15]

# ============================================================
#  RANDOM DATA
# ============================================================
def generate_random_user_id():
    return f"Google|{str(uuid.uuid4())}"

DEVICES = ["ASUS_AI2401_A", "SM-G998B", "CPH2095", "Pixel 6", "OnePlus 9 Pro"]
CARRIERS = ["Jio", "Airtel", "Vodafone", "BSNL"]
CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"]
GPUS = ["Adreno 640", "Mali-G78", "Adreno 660", "Mali-G610"]

def random_device_info():
    return random.choice(DEVICES), random.choice(CARRIERS), random.choice(CITIES), random.choice(GPUS)

_UA_MSDK = None
_UA_UNITY = None

def random_user_agent_msdk():
    global _UA_MSDK
    if _UA_MSDK:
        return _UA_MSDK
    device = random.choice(DEVICES)
    version = random.choice(["11", "12", "13"])
    lang = random.choice(["en", "hi"])
    region = random.choice(["US", "IND"])
    _UA_MSDK = f"GarenaMSDK/4.0.42({device} ;Android {version};{lang};{region};app 2.127.1 2019118047;)"
    return _UA_MSDK

def random_user_agent_unity():
    global _UA_UNITY
    if _UA_UNITY:
        return _UA_UNITY
    _UA_UNITY = "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"
    return _UA_UNITY

_IP_CACHE = "1.2.3.4"
def get_public_ip(session=None):
    global _IP_CACHE
    return _IP_CACHE

# ============================================================
#  PROTOBUF HELPERS
# ============================================================
def varint_encode(n):
    out = []
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)

def build_field(field_num, value):
    if isinstance(value, int):
        return varint_encode((field_num << 3) | 0) + varint_encode(value)
    elif isinstance(value, (str, bytes)):
        data = value.encode('utf-8') if isinstance(value, str) else value
        return varint_encode((field_num << 3) | 2) + varint_encode(len(data)) + data
    elif isinstance(value, dict):
        sub = assemble_proto(value)
        return varint_encode((field_num << 3) | 2) + varint_encode(len(sub)) + sub
    raise TypeError

def assemble_proto(fields):
    packet = b''
    for k, v in fields.items():
        idx = int(k)
        if isinstance(v, list):
            for item in v:
                packet += build_field(idx, item)
        else:
            packet += build_field(idx, v)
    return packet

def aes_encrypt(plain):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    pad_len = 16 - (len(plain) % 16)
    if pad_len == 0:
        pad_len = 16
    return cipher.encrypt(plain + bytes([pad_len]) * pad_len)

def parse_proto(data):
    from google.protobuf.internal.decoder import _DecodeVarint, _DecodeVarint32
    pos, length = 0, len(data)
    result = {}
    while pos < length:
        key, pos = _DecodeVarint(data, pos)
        field = key >> 3
        wire = key & 7
        if wire == 0:
            val, pos = _DecodeVarint(data, pos)
        elif wire == 2:
            size, pos = _DecodeVarint32(data, pos)
            raw = data[pos:pos+size]
            pos += size
            try:
                val = parse_proto(raw)
            except:
                try:
                    val = raw.decode('utf-8')
                except:
                    val = raw.hex()
        elif wire == 5:
            val = int.from_bytes(data[pos:pos+4], 'little')
            pos += 4
        elif wire == 1:
            val = int.from_bytes(data[pos:pos+8], 'little')
            pos += 8
        else:
            raise Exception
        if field in result:
            if not isinstance(result[field], list):
                result[field] = [result[field]]
            result[field].append(val)
        else:
            result[field] = val
    return result

# ============================================================
#  API FUNCTIONS
# ============================================================
def create_session():
    s = requests.Session()
    s.verify = False
    s.timeout = 8
    return s

def register_guest(session, password):
    url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
    payload = {"app_id":100067, "client_type":2, "password":password, "source":2}
    headers = {"User-Agent": random_user_agent_msdk(), "Accept": "application/json",
               "Content-Type": "application/json; charset=utf-8", "Accept-Encoding": "gzip",
               "Connection": "Keep-Alive"}
    resp = session.post(url, json=payload, headers=headers, timeout=8)
    if resp.status_code != 200:
        resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Register failed: {data}")
    return str(data["data"]["uid"])

def token_grant(session, uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    payload = {"uid": str(uid), "password": password, "response_type": "token",
               "client_type": "2", "client_secret": CLIENT_SECRET, "client_id": "100067"}
    headers = {"User-Agent": random_user_agent_msdk(), "Accept": "application/json",
               "Accept-Encoding": "gzip", "Connection": "Keep-Alive"}
    resp = session.post(url, data=payload, headers=headers, timeout=8)
    if resp.status_code != 200:
        resp.raise_for_status()
    data = resp.json()
    access_token = data.get('access_token')
    open_id = data.get('open_id')
    if not access_token or not open_id:
        raise Exception(f"Token grant failed: {data}")
    return access_token, open_id

def major_register(session, nick_prefix, access_token, open_id, region="BD"):
    url = "https://loginbp.ggpolarbear.com/MajorRegister"
    nickname = generate_clean_nickname(nick_prefix)
    lang = "bn"
    xor_key = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
               0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    encoded = ''.join(chr(ord(c) ^ xor_key[i % len(xor_key)]) for i, c in enumerate(open_id))
    unicode_esc = ''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in encoded)
    field_bytes = codecs.decode(unicode_esc, 'unicode_escape').encode('latin1')
    fields = {"1": nickname, "2": access_token, "3": open_id, "5": 102000007, "6": 4,
              "7": 1, "13": 1, "14": field_bytes, "15": lang, "16": 2, "20": "2.127.16", "21": 1}
    plain = assemble_proto(fields)
    encrypted = aes_encrypt(plain)
    headers = {"Accept-Encoding":"gzip", "Authorization":"Bearer", "Connection":"Keep-Alive",
               "Content-Type":"application/x-www-form-urlencoded", "Expect":"100-continue",
               "Host": url.split('/')[2], "ReleaseVersion":"OB54",
               "User-Agent": random_user_agent_unity(), "X-GA":"v1 1", "X-Unity-Version":"2022.3.47f1"}
    resp = session.post(url, headers=headers, data=encrypted, timeout=8)
    if resp.status_code != 200:
        resp.raise_for_status()
    return parse_proto(resp.content)

def major_login(session, access_token, open_id, region="BD", lang="bn"):
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model, carrier, city, gpu = random_device_info()
    ip = get_public_ip(session)
    user_id = generate_random_user_id()
    def q(n):
        out=[]
        while True:
            b = n & 0x7F
            n >>= 7
            if n: b |= 0x80
            out.append(b)
            if not n: break
        return bytes(out)
    def fi(f, v): return q((f<<3)|0) + q(v)
    def fs(f, v):
        data = v.encode() if isinstance(v, str) else v
        return q((f<<3)|2) + q(len(data)) + data

    fields = {3: now, 4: "free fire", 5: 1, 7: "2.127.13",
        8: "Android OS 5.1.1 / API-22 (LMY48Z/rel.se.infra.20220128.171448)",
        9: "Handheld", 10: carrier, 11: "WIFI", 17: gpu, 18: "OpenGL ES 3.0",
        19: user_id, 20: ip, 21: lang, 22: open_id, 23: 4, 24: "Handheld",
        25: model, 26: region.upper(), 29: access_token, 33: carrier,
        34: "WIFI", 37: "7428b253defc164018c604a1ebbfebdf",
        73: "/data/app/com.dts.freefireth-1/lib/arm",
        75: "H4c322aeb56444feaa151d1ea91a8f7f2|/data/app/com.dts.freefireth-1/base.apk",
        76: 2, 78: 2, 79: 2, 83: "OpenGLES2", 85: city, 87: "android",
        88: "KqsHTywQqGHMgPbDY9P2mhkxXj/beObk/TFNpmgaucQwxyLu9hA478WEQCV0Mgaz9UivYUPpKNwPzgZhvDhSsUDMAFY=",
        90: '{"cur_rate":null,"support_etc2":false}', 97: 1, 98: 1, 99: "4", 100: "4"}
    packet = b''
    for k, v in fields.items():
        if isinstance(v, int):
            packet += fi(k, v)
        elif isinstance(v, (str, bytes)):
            packet += fs(k, v)
    encrypted = aes_encrypt(packet)
    headers = {"Accept-Encoding":"gzip", "Connection":"Keep-Alive",
               "Content-Type":"application/x-www-form-urlencoded", "Expect":"100-continue",
               "ReleaseVersion":"OB54", "User-Agent": random_user_agent_unity(),
               "X-GA":"v1 1", "X-Unity-Version":"2022.3.47f1"}
    resp = session.post(url, headers=headers, data=encrypted, timeout=8)
    if resp.status_code != 200:
        resp.raise_for_status()
    decoded = parse_proto(resp.content)
    jwt = decoded.get(8)
    if isinstance(jwt, list):
        jwt = jwt[0]
    return decoded, jwt

def choose_region(session, region, jwt):
    url = "https://loginbp.ggblueshark.com/ChooseRegion"
    fields = {"1": region.upper()}
    plain = assemble_proto(fields)
    encrypted = aes_encrypt(plain)
    headers = {"Accept-Encoding":"gzip", "Authorization":f"Bearer {jwt}",
               "Connection":"Keep-Alive", "Content-Type":"application/x-www-form-urlencoded",
               "Expect":"100-continue", "Host": url.split('/')[2], "ReleaseVersion":"OB54",
               "User-Agent": random_user_agent_unity(), "X-GA":"v1 1", "X-Unity-Version":"2022.3.47f1"}
    resp = session.post(url, headers=headers, data=encrypted, timeout=8)
    return resp.status_code == 200

def decode_nickname(jwt):
    try:
        parts = jwt.split('.')
        payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
        data = json.loads(base64.b64decode(payload))
        raw = data.get("nickname")
        if raw:
            decoded = base64.b64decode(raw)
            nick = bytes([decoded[i] ^ NICK_XOR_KEY[i % len(NICK_XOR_KEY)] for i in range(len(decoded))])
            nick = nick.decode('utf-8', errors='ignore')
        else:
            nick = ""
        return nick
    except:
        return None

# ============================================================
#  PROGRESS BAR
# ============================================================
def progress_bar(current, total, length=25):
    if total == 0:
        return
    percent = 100 * (current / float(total))
    filled = int(length * current // total)
    bar = f"{GREEN}{'█' * filled}{RESET}{'░' * (length - filled)}"
    return f"\rProgress {bar} {BOLD}{percent:.0f}%{RESET} {current}/{total}"

# ============================================================
#  GENERATOR
# ============================================================
class MehediGenerator:
    def __init__(self, region, prefix, total, threads):
        self.region = region.upper()
        self.prefix = prefix.upper()
        self.total = total
        self.threads = threads
        self.completed = 0
        self.failed = 0
        self.results = []
        self.lock = threading.Lock()
        self.start_time = None

    def _generate_account(self, thread_id):
        session = create_session()
        plain_pass = generate_hex_password()
        nickname = generate_clean_nickname(self.prefix)
        region = self.region

        try:
            uid = register_guest(session, plain_pass)
            access_token, open_id = token_grant(session, uid, plain_pass)
            reg_resp = major_register(session, self.prefix, access_token, open_id, region)
            game_uid = str(reg_resp.get(3))
            login_resp, jwt = major_login(session, access_token, open_id, region, "bn")
            nickname_dec = decode_nickname(jwt) or nickname
            choose_region(session, region, jwt)
            
            return {"uid": uid, "game_uid": game_uid, "password": plain_pass,
                    "nickname": nickname_dec, "region": region, "thread": thread_id}
        except:
            return None

    def _worker(self, thread_id):
        while self.completed + self.failed < self.total:
            acc = self._generate_account(thread_id)
            if acc:
                with self.lock:
                    self.completed += 1
                    self.results.append(acc)
                    current = self.completed
                    total = self.total
                self._print_success(current, total, acc)
                self._save_account(acc)
            else:
                with self.lock:
                    self.failed += 1

    def _print_success(self, current, total, acc):
        elapsed = time.time() - self.start_time if self.start_time else 0
        speed = current / elapsed if elapsed > 0 else 0
        bar = progress_bar(current, total)
        if bar:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

        print(f"""
{BOLD}{GREEN}✅ ACCOUNT #{current}/{total} GENERATED!{RESET}
  🆔 UID: {acc['uid']}
  🔑 PASS: {YELLOW}{acc['password']}{RESET}
  👤 NAME: {PURPLE}{acc['nickname']}{RESET}
  🎮 ID: {acc['game_uid']}
  🌍 REGION: {acc['region']}
  {bar}  ⚡ {speed:.2f} acc/s
""")

    def _save_account(self, acc):
        with self.lock:
            try:
                with open("accounts.json", "r") as f:
                    data = json.load(f)
            except:
                data = []
            data.append(acc)
            with open("accounts.json", "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def start(self):
        print_banner()
        print(f"""
{BOLD}{GREEN}╔══════════════════════════════════════════════════════╗
║           EXTREME FAST CONFIGURATION                      ║
╠══════════════════════════════════════════════════════╣
║  🌍 Region: {self.region:<43} ║
║  👤 Name Prefix: {self.prefix:<41} ║
║  📊 Accounts: {self.total:<40} ║
║  ⚙️  Threads: {self.threads:<42} ║
║  ⚡ Mode: EXTREME FAST{' ' * (37)} ║
╚══════════════════════════════════════════════════════╝{RESET}
""")
        print(f"{BOLD}{GREEN}⚡ STARTING {self.threads} WORKERS... ⚡{RESET}\n")

        self.start_time = time.time()

        try:
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                futures = [executor.submit(self._worker, i) for i in range(self.threads)]
                for future in as_completed(futures):
                    pass
        except KeyboardInterrupt:
            print(f"\n⚠️ Stopped by user")

        elapsed = time.time() - self.start_time
        saved = len(self.results)
        rate = saved / elapsed if elapsed > 0 else 0
        print(f"""
{BOLD}{GREEN}╔══════════════════════════════════════════════════════╗
║              ✅ GENERATION COMPLETE!                      ║
╠══════════════════════════════════════════════════════╣
║  📊 Generated: {saved:<40} ║
║  ❌ Failed: {self.failed:<43} ║
║  ⏱️  Time: {elapsed:.1f}s{' ' * (43 - len(f'{elapsed:.1f}s'))}║
║  ⚡ Speed: {rate:.2f} acc/s{' ' * (42 - len(f'{rate:.2f} acc/s'))}║
║  📁 Saved: accounts.json{' ' * (41)}║
╚══════════════════════════════════════════════════════╝{RESET}
""")

# ============================================================
#  MAIN
# ============================================================
def main():
    print_banner()
    print("-"*60)

    # ============================================================
    #  TAKE NAME INPUT
    # ============================================================
    print(f"{BOLD}{CYAN}📋 ENTER YOUR PREFERRED NAME{RESET}")
    print(f"{BOLD}{YELLOW}💡 Name will be used as prefix for all accounts{RESET}")
    print(f"{BOLD}{YELLOW}💡 Example: Enter 'MEHEDI' → Names will be MEHEDI⁰¹²³⁴{RESET}")
    print("-"*60)
    
    name_prefix = input(f"{BOLD}👤 Enter name prefix (default MEHEDI): {RESET}").strip() or "MEHEDI"
    name_prefix = name_prefix.upper()
    
    print(f"\n{BOLD}{GREEN}✅ Using name prefix: {PURPLE}{name_prefix}{RESET}")
    print("-"*60)

    try:
        total = int(input(f"{BOLD}🔢 How many accounts? (default 10): {RESET}").strip() or "10")
    except:
        total = 10

    try:
        threads = int(input(f"{BOLD}⚙️  Threads (10-50, default 20): {RESET}").strip() or "20")
        threads = max(10, min(threads, 50))
    except:
        threads = 20

    print(f"""
{BOLD}{YELLOW}⚠️  VPN ON for best results!{RESET}
{BOLD}{YELLOW}💡  Password: 64 CHAR HEX{RESET}
{BOLD}{YELLOW}💡  Name: {PURPLE}{name_prefix}{RESET}{YELLOW} + Superscript Numbers{RESET}
{BOLD}{YELLOW}💡  Accounts saved to accounts.json{RESET}
""")

    input(f"{BOLD}{GREEN}Press ENTER to start generation...{RESET}")

    generator = MehediGenerator("BD", name_prefix, total, threads)
    generator.start()

if __name__ == "__main__":
    main()
