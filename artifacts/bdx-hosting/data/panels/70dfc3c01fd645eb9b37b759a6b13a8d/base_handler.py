# bot/packets/base_handler.py
# ============================================================
# RAFIN's Base Packet Handler - Free Fire Protocol Helpers
# ============================================================

import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from protobuf_decoder.protobuf_decoder import Parser

async def EnC_PacKeT(HeX, K, V):
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()

async def DEc_PacKeT(hex_string, key, iv):
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(bytes.fromhex(hex_string))
        return unpad(decrypted, AES.block_size).hex()
    except:
        return None

async def encrypted_proto(serialized_payload):
    k = b'Yg&tc%DEuh6%Zc^8'
    i = b'6oyZDr22E3ychjM%'
    cipher = AES.new(k, AES.MODE_CBC, i)
    return cipher.encrypt(pad(serialized_payload, AES.block_size))

# --- Protobuf Helpers ---
async def EnC_Vr(N):
    if N < 0: return b''
    H = []
    while True:
        BesTo = N & 0x7F; N >>= 7
        if N: BesTo |= 0x80
        H.append(BesTo)
        if not N: break
    return bytes(H)

async def CrEaTe_VarianT(f, v):
    return await EnC_Vr((f << 3) | 0) + await EnC_Vr(v)

async def CrEaTe_LenGTh(f, v):
    encoded = v.encode() if isinstance(v, str) else v
    return await EnC_Vr((f << 3) | 2) + await EnC_Vr(len(encoded)) + encoded

async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet

async def DecodE_HeX(val):
    if val is None: return ''
    h = hex(val)[2:]
    return '0' * (len(h) % 2) + h

async def GeneRaTePk(Pk, N, K, V):
    PkEnc = await EnC_PacKeT(Pk, K, V)
    size_hex = await DecodE_HeX(int(len(PkEnc) // 2))
    pad_len = len(size_hex)
    
    if pad_len == 2: HeadEr = N + "000000"
    elif pad_len == 3: HeadEr = N + "00000"
    elif pad_len == 4: HeadEr = N + "0000"
    elif pad_len == 5: HeadEr = N + "000"
    else: HeadEr = N + "000"
    
    return bytes.fromhex(HeadEr + size_hex + PkEnc)

async def Fix_PackEt(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data['wire_type'] = result.wire_type
        if result.wire_type == "varint":
            field_data['data'] = result.data
        if result.wire_type == "string":
            field_data['data'] = result.data
        if result.wire_type == "bytes":
            field_data['data'] = result.data
        elif result.wire_type == 'length_delimited':
            field_data["data"] = await Fix_PackEt(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

async def DeCode_PackEt(input_text):
    try:
        parsed = Parser().parse(input_text)
        parsed_dict = await Fix_PackEt(parsed)
        return json.dumps(parsed_dict)
    except:
        return None