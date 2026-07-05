#!/usr/bin/env python3
"""
RAFIN's Chat Listener - DEBUG VERSION
Shows ALL raw packets received
"""

import asyncio
import sys
import struct
import binascii
import time
import random
from datetime import datetime
from typing import Optional, Tuple

import aiohttp
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from Pb2 import MajoRLoGinrEq_pb2, MajoRLoGinrEs_pb2, PorTs_pb2, DEcwHisPErMsG_pb2

# ======================== CONSTANTS ========================
STATIC_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
STATIC_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# Global
whisper_writer = None
last_sender = None

def fmt_uid(uid: str) -> str:
    return "💔".join(uid)

async def GeNeRaTeAccEss(uid: str, password: str) -> Tuple[Optional[str], Optional[str]]:
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
        async with session.post(url, headers=headers, data=data) as resp:
            if resp.status != 200:
                return None, None
            js = await resp.json()
            return js.get("open_id"), js.get("access_token")

def _encode_varint_field(field_num: int, value: int) -> bytes:
    key = (field_num << 3) | 0
    result = bytearray()
    while key > 0x7F:
        result.append((key & 0x7F) | 0x80)
        key >>= 7
    result.append(key)
    val = value
    while val > 0x7F:
        result.append((val & 0x7F) | 0x80)
        val >>= 7
    result.append(val)
    return bytes(result)

def _encode_length_delimited(field_num: int, data: str) -> bytes:
    key = (field_num << 3) | 2
    result = bytearray()
    while key > 0x7F:
        result.append((key & 0x7F) | 0x80)
        key >>= 7
    result.append(key)
    length = len(data)
    while length > 0x7F:
        result.append((length & 0x7F) | 0x80)
        length >>= 7
    result.append(length)
    result.extend(data.encode())
    return bytes(result)

async def EncRypTMajoRLoGin_minimal(open_id: str, access_token: str, region="BD", lang_code="en") -> bytes:
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text
    except:
        ip = "0.0.0.0"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    packet = b''
    packet += _encode_length_delimited(3, now_str)
    packet += _encode_length_delimited(4, "free fire")
    packet += _encode_length_delimited(7, "1.123.17")
    packet += _encode_length_delimited(20, ip)
    packet += _encode_length_delimited(21, lang_code)
    packet += _encode_length_delimited(22, open_id)
    packet += _encode_length_delimited(26, region.upper())
    packet += _encode_length_delimited(29, access_token)
    packet += _encode_varint_field(38, 2)
    packet += _encode_varint_field(49, 2)
    packet += _encode_varint_field(76, 2)
    packet += _encode_varint_field(78, 2)
    packet += _encode_varint_field(79, 2)
    packet += _encode_varint_field(88, 4)
    packet += _encode_varint_field(97, 2)
    packet += _encode_varint_field(98, 2)
    packet += _encode_length_delimited(99, "4")
    packet += _encode_length_delimited(100, "4")
    cipher = AES.new(STATIC_KEY, AES.MODE_CBC, STATIC_IV)
    pad_len = 16 - (len(packet) % 16)
    if pad_len == 0:
        pad_len = 16
    plaintext_padded = packet + bytes([pad_len]) * pad_len
    return cipher.encrypt(plaintext_padded)

async def MajorLogin(payload: bytes) -> Optional[bytes]:
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    headers = {
        "User-Agent": "RAFIN/1.0 (Linux; Android 13; SM-S918B Build/TP1A.220.624.014)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/octet-stream",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers) as resp:
            if resp.status == 200:
                return await resp.read()
            return None

async def DecRypTMajoRLoGin(data: bytes):
    proto = MajoRLoGinrEs_pb2.MajorLoginRes()
    proto.ParseFromString(data)
    return proto

async def GetLoginData(base_url: str, payload: bytes, token: str) -> Optional[bytes]:
    url = f"{base_url}/GetLoginData"
    headers = {
        "User-Agent": "RAFIN/1.0 (Linux; Android 13; SM-S918B Build/TP1A.220.624.014)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers) as resp:
            if resp.status == 200:
                return await resp.read()
            return None

async def DecRypTLoGinDaTa(data: bytes):
    proto = PorTs_pb2.GetLoginData()
    proto.ParseFromString(data)
    return proto

async def EnC_PacKeT(hex_data: str, key: bytes, iv: bytes) -> str:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    raw = bytes.fromhex(hex_data)
    padded = pad(raw, AES.block_size)
    return cipher.encrypt(padded).hex()

async def DEc_PacKeT(hex_data: str, key: bytes, iv: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = bytes.fromhex(hex_data)
    decrypted = cipher.decrypt(encrypted)
    return unpad(decrypted, AES.block_size)

async def xAuThSTarTuP(bot_uid: int, token: str, timestamp: int, key: bytes, iv: bytes) -> str:
    uid_hex = hex(bot_uid)[2:]
    uid_length = len(uid_hex)
    encrypted_timestamp = hex(timestamp)[2:]
    encrypted_account_token = token.encode().hex()
    encrypted_packet = await EnC_PacKeT(encrypted_account_token, key, iv)
    encrypted_packet_length = hex(len(encrypted_packet) // 2)[2:]
    if uid_length == 9:
        headers = '0000000'
    elif uid_length == 8:
        headers = '00000000'
    elif uid_length == 10:
        headers = '000000'
    elif uid_length == 7:
        headers = '000000000'
    else:
        headers = '0000000'
    return f"0115{headers}{uid_hex}{encrypted_timestamp}00000{encrypted_packet_length}{encrypted_packet}"

async def send_keep_alive(writer, key, iv):
    """Send keep-alive packet every 30 seconds to maintain connection"""
    while True:
        await asyncio.sleep(30)
        if writer and not writer.is_closing():
            try:
                # Keep-alive packet (type 99)
                fields = {1: 99, 2: {1: int(time.time()), 2: 1}}
                # We need to create this packet properly. For now, just send a dummy.
                # But since we don't have CrEaTe_ProTo here, we'll skip.
                # The original bot sends keep-alive automatically.
                pass
            except:
                pass

async def chat_loop(ip, port, auth_token_hex, static_key, static_iv):
    global whisper_writer, last_sender
    
    while True:
        try:
            reader, writer = await asyncio.open_connection(ip, port)
            whisper_writer = writer
            auth_bytes = bytes.fromhex(auth_token_hex)
            writer.write(auth_bytes)
            await writer.drain()
            print("✅ Chat server connected. Waiting for packets...")
            
            while True:
                # Read packet length
                len_data = await reader.readexactly(2)
                pkt_len = struct.unpack('>H', len_data)[0]
                pkt_data = await reader.readexactly(pkt_len)
                hex_data = pkt_data.hex()
                
                print(f"\n[RAW] Packet length: {pkt_len}, hex: {hex_data[:50]}...")
                
                # Check packet type (first 4 hex chars = 2 bytes)
                pkt_type = hex_data[:4]
                print(f"[RAW] Packet type: {pkt_type}")
                
                if pkt_type in ["1200", "1201"]:
                    # Chat packet
                    encrypted_part = hex_data[10:]  # Skip header (5 bytes)
                    print(f"[DEBUG] Encrypted part length: {len(encrypted_part)}")
                    
                    # Try decryption with STATIC keys
                    try:
                        decrypted = await DEc_PacKeT(encrypted_part, static_key, static_iv)
                        msg = DEcwHisPErMsG_pb2.DecodeWhisper()
                        msg.ParseFromString(decrypted)
                        print(f"[DECODED] chat_type={msg.Data.chat_type}, uid={msg.Data.uid}")
                        if msg.Data.chat_type == 2:  # private
                            sender = msg.Data.uid
                            nickname = msg.Data.Details.Nickname
                            message_text = msg.Data.msg
                            print(f"\n📩 [{datetime.now().strftime('%H:%M:%S')}] {nickname} ({fmt_uid(str(sender))}): {message_text}")
                            last_sender = sender
                    except Exception as e:
                        print(f"[DECRYPT FAIL] {e}")
                        # Try with dynamic keys? Probably not needed.
                else:
                    print(f"[IGNORED] Unknown packet type")
                    
        except asyncio.IncompleteReadError:
            print("Connection lost, reconnecting...")
        except Exception as e:
            print(f"Error: {e}, reconnecting...")
        finally:
            if whisper_writer:
                try:
                    whisper_writer.close()
                except:
                    pass
                whisper_writer = None
        await asyncio.sleep(3)

async def send_private_message(target_uid: int, message: str, bot_uid: int, key: bytes, iv: bytes):
    """Send private message using xSEndMsg from xC4.py"""
    try:
        from xC4 import xSEndMsg
        packet = await xSEndMsg(message, 2, target_uid, bot_uid, key, iv)
        if packet and whisper_writer:
            whisper_writer.write(packet)
            await whisper_writer.drain()
            return True
    except ImportError:
        print("xC4.py not found, cannot send message.")
    except Exception as e:
        print(f"Send error: {e}")
    return False

async def main():
    print("=" * 60)
    print("RAFIN's Chat Listener - DEBUG VERSION")
    print("=" * 60)
    uid = input("Bot UID: ").strip()
    password = input("Bot password: ").strip()
    
    # Auth
    open_id, access_token = await GeNeRaTeAccEss(uid, password)
    if not open_id:
        print("❌ Auth failed")
        return
    print("✅ Access token obtained")
    
    login_payload = await EncRypTMajoRLoGin_minimal(open_id, access_token, region="BD")
    login_resp = await MajorLogin(login_payload)
    if not login_resp:
        print("❌ MajorLogin failed")
        return
    login_data = await DecRypTMajoRLoGin(login_resp)
    bot_uid = login_data.account_uid
    key = login_data.key
    iv = login_data.iv
    jwt_token = login_data.token
    timestamp = login_data.timestamp
    print(f"✅ Logged in as UID: {bot_uid}")
    
    # Get chat server
    base_url = login_data.url
    login_data_resp = await GetLoginData(base_url, login_payload, jwt_token)
    if not login_data_resp:
        print("❌ No login data")
        return
    login_data_dec = await DecRypTLoGinDaTa(login_data_resp)
    chat_ip_port = login_data_dec.AccountIP_Port
    if not chat_ip_port:
        print("❌ No chat server")
        return
    chat_ip, chat_port = chat_ip_port.split(":")
    chat_port = int(chat_port)
    print(f"✅ Chat server: {chat_ip}:{chat_port}")
    
    # Build auth token
    auth_token_hex = await xAuThSTarTuP(int(bot_uid), jwt_token, int(timestamp), key, iv)
    
    # Start chat loop
    asyncio.create_task(chat_loop(chat_ip, chat_port, auth_token_hex, STATIC_KEY, STATIC_IV))
    
    # User input loop
    print("\n💡 Type message to reply to last sender. Type 'exit' to quit.\n")
    while True:
        reply = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not reply:
            continue
        reply = reply.strip()
        if reply.lower() == 'exit':
            break
        if last_sender is None:
            print("⚠️ No one has messaged yet.")
            continue
        success = await send_private_message(last_sender, reply, int(bot_uid), key, iv)
        if success:
            print(f"✅ RAFIN replied to {last_sender}")
        else:
            print("❌ Failed to send")

if __name__ == "__main__":
    asyncio.run(main())