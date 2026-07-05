import json, binascii, time, random, asyncio, logging
from protobuf_decoder.protobuf_decoder import Parser
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

Key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
Iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

async def EnC_AEs(HeX):
    cipher = AES.new(Key, AES.MODE_CBC, Iv)
    return cipher.encrypt(pad(bytes.fromhex(HeX), AES.block_size)).hex()

async def DEc_AEs(HeX):
    cipher = AES.new(Key, AES.MODE_CBC, Iv)
    return unpad(cipher.decrypt(bytes.fromhex(HeX)), AES.block_size).hex()

async def EnC_PacKeT(HeX, K, V):
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()

async def DEc_PacKeT(HeX, K, V):
    return unpad(AES.new(K, AES.MODE_CBC, V).decrypt(bytes.fromhex(HeX)), 16).hex()

async def encrypt_packet(packet_hex, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(bytes.fromhex(packet_hex), AES.block_size)
    return cipher.encrypt(padded).hex()

async def EnC_Uid(H, Tp):
    e, H = [], int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0))
        H >>= 7
    return bytes(e).hex() if Tp == 'Uid' else None

async def EnC_Vr(N):
    if N < 0:
        return b''
    H = []
    while True:
        BesTo = N & 0x7F
        N >>= 7
        if N:
            BesTo |= 0x80
        H.append(BesTo)
        if not N:
            break
    return bytes(H)

def DEc_Uid(H):
    n = s = 0
    for b in bytes.fromhex(H):
        n |= (b & 0x7F) << s
        if not b & 0x80:
            break
        s += 7
    return n

async def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return await EnC_Vr(field_header) + await EnC_Vr(value)

async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return await EnC_Vr(field_header) + await EnC_Vr(len(encoded_value)) + encoded_value

async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet

async def DecodE_HeX(H):
    R = hex(H)
    F = str(R)[2:]
    if len(F) == 1:
        F = "0" + F
    return F

async def Fix_PackEt(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {'wire_type': result.wire_type}
        if result.wire_type in ("varint", "string", "bytes"):
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
    except Exception as e:
        print(f"DeCode_PackEt error: {e}")
        return None

async def base_to_hex(timestamp):
    result = hex(timestamp)[2:]
    return "0" + result if len(result) == 1 else result

async def GeneRaTePk(packet_hex, packet_type, K, V):
    try:
        encrypted = await encrypt_packet(packet_hex, K, V)
        pkt_len = len(encrypted) // 2
        len_hex = await base_to_hex(pkt_len)
        if len(len_hex) == 2:
            header = f"{packet_type}000000"
        elif len(len_hex) == 3:
            header = f"{packet_type}00000"
        elif len(len_hex) == 4:
            header = f"{packet_type}0000"
        elif len(len_hex) == 5:
            header = f"{packet_type}000"
        else:
            header = f"{packet_type}00"
        return bytes.fromhex(header + len_hex + encrypted)
    except Exception as e:
        logging.error(f"GeneRaTePk error: {e}")
        return None

def fixnum(num):
    num_str = str(num)
    return "[C]" + "[C]".join(num_str) + "[C]"

async def Ua():
    versions = ['4.0.18P6', '4.0.19P7', '4.0.20P1', '4.1.0P3', '4.1.5P2', '4.2.1P8',
                '4.2.3P1', '5.0.1B2', '5.0.2P4', '5.1.0P1', '5.2.0B1', '5.2.5P3',
                '5.3.0B1', '5.3.2P2', '5.4.0P1', '5.4.3B2', '5.5.0P1', '5.5.2P3']
    models = ['SM-A125F', 'SM-A225F', 'SM-A325M', 'SM-A515F', 'SM-A725F', 'SM-M215F', 'SM-M325FV',
              'Redmi 9A', 'Redmi 9C', 'POCO M3', 'POCO M4 Pro', 'RMX2185', 'RMX3085',
              'moto g(9) play', 'CPH2239', 'V2027', 'OnePlus Nord', 'ASUS_Z01QD']
    android_versions = ['9', '10', '11', '12', '13', '14']
    languages = ['en-US', 'es-MX', 'pt-BR', 'id-ID', 'ru-RU', 'hi-IN']
    countries = ['USA', 'MEX', 'BRA', 'IDN', 'RUS', 'IND']
    return f"GarenaMSDK/{random.choice(versions)}({random.choice(models)};Android {random.choice(android_versions)};{random.choice(languages)};{random.choice(countries)};)"

def Uaa():
    versions = ['4.0.18P6', '4.0.19P7', '4.0.20P1', '4.1.0P3', '4.1.5P2', '4.2.1P8',
                '4.2.3P1', '5.0.1B2', '5.0.2P4', '5.1.0P1', '5.2.0B1', '5.2.5P3',
                '5.3.0B1', '5.3.2P2', '5.4.0P1', '5.4.3B2', '5.5.0P1', '5.5.2P3']
    models = ['SM-A125F', 'SM-A225F', 'SM-A325M', 'SM-A515F', 'SM-A725F', 'SM-M215F', 'SM-M325FV',
              'Redmi 9A', 'Redmi 9C', 'POCO M3', 'POCO M4 Pro', 'RMX2185', 'RMX3085',
              'moto g(9) play', 'CPH2239', 'V2027', 'OnePlus Nord', 'ASUS_Z01QD']
    android_versions = ['9', '10', '11', '12', '13', '14']
    languages = ['en-US', 'es-MX', 'pt-BR', 'id-ID', 'ru-RU', 'hi-IN']
    countries = ['USA', 'MEX', 'BRA', 'IDN', 'RUS', 'IND']
    return f"GarenaMSDK/{random.choice(versions)}({random.choice(models)};Android {random.choice(android_versions)};{random.choice(languages)};{random.choice(countries)};)"

async def ArA_CoLor():
    colors = ["32CD32", "00BFFF", "00FA9A", "90EE90", "FF4500", "FF6347", "FF69B4", "FF8C00",
              "FFD700", "FFDAB9", "F0F0F0", "F0E68C", "D3D3D3", "A9A9A9", "D2691E", "CD853F",
              "BC8F8F", "6A5ACD", "483D8B", "4682B4", "9370DB", "C71585", "FF8C00", "FFA07A"]
    return random.choice(colors)

def get_random_avatar():
    avatars = [902000204, 902000191, 902038023, 902031017, 902030016, 902039014,
               902000063, 902052025, 902052007, 902052026, 902052006, 902052010,
               902000281, 902000345, 902034018, 902034019]
    return random.choice(avatars)

def get_random_colour():
    colors = ["[FF0000]", "[00FF00]", "[0000FF]", "[FFFF00]", "[FF00FF]", "[00FFFF]", "[FFFFFF]", "[FFA500]",
              "[A52A2A]", "[800080]", "[000000]", "[808080]", "[C0C0C0]", "[FFC0CB]", "[FFD700]", "[ADD8E6]",
              "[90EE90]", "[D2691E]", "[DC143C]", "[00CED1]", "[9400D3]", "[F08080]", "[20B2AA]", "[FF1493]",
              "[7CFC00]", "[B22222]", "[FF4500]", "[DAA520]", "[00BFFF]", "[00FF7F]", "[4682B4]", "[6495ED]",
              "[5F9EA0]", "[DDA0DD]", "[E6E6FA]", "[B0C4DE]", "[556B2F]", "[8FBC8F]", "[2E8B57]", "[3CB371]",
              "[6B8E23]", "[808000]", "[B8860B]", "[CD5C5C]", "[8B0000]", "[FF6347]", "[FF8C00]", "[BDB76B]",
              "[9932CC]", "[8A2BE2]", "[4B0082]", "[6A5ACD]", "[7B68EE]", "[4169E1]", "[1E90FF]", "[191970]",
              "[00008B]", "[000080]", "[008080]", "[008B8B]", "[B0E0E6]", "[AFEEEE]", "[E0FFFF]", "[F5F5DC]",
              "[FAEBD7]"]
    return random.choice(colors)

async def xSEndMsg(Msg, Tp, Tp2, target_id, K, V):
    feilds = {
        1: target_id,  # Target UID
        2: Tp2,        # Chat ID
        3: Tp,         # Chat type (1=whisper, 2=group)
        4: Msg,        # Message content
        5: int(time.time()),  # Current timestamp
        7: 2,
        9: {
            1: "xBesTo - C4", 
            2: int(get_random_avatar()), 
            3: 901048020, 
            4: 330, 
            5: 1001000001, 
            8: "xBesTo - C4", 
            10: 1, 
            11: 1, 
            13: {1: 2}, 
            14: {1: 12484827014, 2: 8, 3: b"\x10\x15\x08\n\x0b\x13\f\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}, 
            12: 0
        }, 
        10: "en", 
        13: {3: 1}
    }    
    Pk = (await CrEaTe_ProTo(feilds)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)
    
async def xSEndMsgsQ(Msg, id, K, V, region="BD"):
    avatar = get_random_avatar()
    fields = {
        1: id, 2: id, 4: Msg, 5: 1756580149, 7: 2, 8: 904990072,
        9: {
            1: "xBe4!sTo - C4", 2: avatar, 4: 329, 5: 1001000001, 8: "xBe4!sTo - C4",
            10: 1, 11: 1, 13: {1: 2},
            14: {1: 1158053040, 2: 8, 3: b"\x10\x15\x08\x0A\x0B\x15\x0C\x0F\x11\x04\x07\x02\x03\x0D\x0E\x12\x01\x05\x06"}
        },
        10: "en", 13: {2: 2, 3: 1},
        14: {1: {1: 3, 2: 7, 3: 170, 4: 999, 5: 1740196800, 6: region}}
    }
    Pk = (await CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)

async def SEndMsG(H, message, target_uid, chat_id, key, iv, region):
    if H == 0:          
        return await xSEndMsgsQ(message, chat_id, key, iv, region)
    elif H == 1:        
        return await xSEndMsg(message, 1, chat_id, target_uid, key, iv)  # Fixed: removed region
    elif H == 2:        
        return await xSEndMsg(message, 2, target_uid, target_uid, key, iv)  # Fixed
    else:
        return await xSEndMsgsQ(message, chat_id, key, iv, region)

async def AuthClan(CLan_Uid, AuTh, K, V):
    fields = {1: 3, 2: {1: int(CLan_Uid), 2: 1, 4: str(AuTh)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1201', K, V)

async def GenJoinSquadsPacket(code, K, V):
    fields = {
        1: 4,
        2: {
            4: bytes.fromhex("01090a0b121920"),
            5: str(code),
            6: 6,
            8: 1,
            9: {2: 800, 6: 11, 8: "1.111.1", 9: 5, 10: 1}
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)

async def OpEnSq(K, V, region):
    fields = {1: 1, 2: {2: "\u0001", 3: 1, 4: 1, 5: "en", 9: 1, 11: 1, 13: 1, 14: {2: 5756, 6: 11, 8: "1.111.5", 9: 2, 10: 4}}}
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def cHSq(Nu, Uid, K, V, region):
    fields = {1: 17, 2: {1: int(Uid), 2: 1, 3: int(Nu - 1), 4: 62, 5: "\u001a", 8: 5, 13: 329}}
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def SEnd_InV(Nu, Uid, K, V, region):
    fields = {1: 2, 2: {1: int(Uid), 2: region, 4: int(Nu)}}
    if region.lower() == "ind":
        packet = '0514'
    elif region.lower() == "bd":
        packet = "0519"
    else:
        packet = "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def ExiT(idT, K, V):
    fields = {1: 7, 2: {1: idT}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)

async def GeTSQDaTa(D):
    uid = D['5']['data']['1']['data']
    chat_code = D["5"]["data"]["17"]["data"]
    squad_code = D["5"]["data"]["31"]["data"]
    return uid, chat_code, squad_code

async def AutH_Chat(T, uid, code, K, V):
    fields = {1: T, 2: {1: uid, 3: "en", 4: str(code)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, V)