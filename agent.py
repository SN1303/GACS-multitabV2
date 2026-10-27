#!/usr/bin/env python3
# ==============================================================================
# ALIJAYA NET - GenieACS AI Telegram Agent (Full Multi-Tab & Operations Mod)
# Pengembang: ALIJAYA NET (WhatsApp: 081947215703)
# ==============================================================================

import os
import sys
import shutil
import re
import time
import json
import logging
import subprocess
import requests
import pymongo
import hmac
import hashlib
import base64
import secrets
from urllib.parse import quote, urlparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from http.server import ThreadingHTTPServer as DefaultHTTPServer
except ImportError:
    from http.server import HTTPServer as DefaultHTTPServer
try:
    from http.server import ThreadingHTTPServer as DefaultHTTPServer
except ImportError:
    from http.server import HTTPServer as DefaultHTTPServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("GenieACSAgent")

_CURRENT_MONGO_CLIENT = None
_RESOLVED_MONGO_URI = None

def resolve_mongo_uri():
    global _RESOLVED_MONGO_URI
    if _RESOLVED_MONGO_URI:
        return _RESOLVED_MONGO_URI

    candidates = []
    if os.environ.get("GENIEACS_MONGODB_CONNECTION_URL"):
        candidates.append(os.environ.get("GENIEACS_MONGODB_CONNECTION_URL"))

    for env_path in ["/opt/genieacs/genieacs.env", "/etc/genieacs.env", "/etc/default/genieacs"]:
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GENIEACS_MONGODB_CONNECTION_URL="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and val not in candidates:
                                candidates.append(val)
            except Exception:
                pass

    for default_uri in [
        "mongodb://genie:genie@127.0.0.1:27017/genieacs",
        "mongodb://genie:genie@127.0.0.1/genieacs",
        "mongodb://127.0.0.1:27017/genieacs",
        "mongodb://127.0.0.1/genieacs",
        "mongodb://localhost:27017/genieacs"
    ]:
        if default_uri not in candidates:
            candidates.append(default_uri)

    for uri in candidates:
        try:
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=1500)
            db_name = "genieacs"
            try:
                p = client.get_default_database()
                if p is not None:
                    db_name = p.name
            except Exception:
                pass
            client[db_name].command("ping")
            _RESOLVED_MONGO_URI = uri
            logger.info(f"MongoDB connected successfully via: {uri.split('@')[-1] if '@' in uri else uri}")
            return uri
        except Exception:
            continue

    _RESOLVED_MONGO_URI = candidates[0] if candidates else "mongodb://genie:genie@127.0.0.1:27017/genieacs"
    return _RESOLVED_MONGO_URI

MONGO_URI = resolve_mongo_uri()
NBI_URL = "http://127.0.0.1:7557"

USER_STATES = {}
SEEN_DEVICES = set()
NOTIFIED_DROPS = {} # device_id -> timestamp

def get_db():
    global _CURRENT_MONGO_CLIENT, _RESOLVED_MONGO_URI
    try:
        if _CURRENT_MONGO_CLIENT is not None:
            try:
                db_name = "genieacs"
                try:
                    p = _CURRENT_MONGO_CLIENT.get_default_database()
                    if p is not None:
                        db_name = p.name
                except Exception:
                    pass
                _CURRENT_MONGO_CLIENT[db_name].command("ping")
                return _CURRENT_MONGO_CLIENT[db_name]
            except Exception:
                _CURRENT_MONGO_CLIENT = None

        uri = resolve_mongo_uri()
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        db_name = "genieacs"
        try:
            p = client.get_default_database()
            if p is not None:
                db_name = p.name
        except Exception:
            pass
        client[db_name].command("ping")
        _CURRENT_MONGO_CLIENT = client
        return client[db_name]
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        _RESOLVED_MONGO_URI = None
        _CURRENT_MONGO_CLIENT = None
        return None

def get_config():
    db = get_db()
    if db is None:
        return {}
    cfgs = db.config.find({"_id": {"$regex": "^agent\\."}})
    res = {}
    for c in cfgs:
        val = str(c.get("value", "")).strip()
        while len(val) >= 2 and ((val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"'))):
            val = val[1:-1].strip()
        res[c["_id"]] = val.strip()
    return res

BRAND_NAME = "ALIJAYA NET"
BRAND_PHONE = "081947215703"

def update_branding(cfgs):
    global BRAND_NAME, BRAND_PHONE
    b_name = cfgs.get("agent.brand.name", "").strip()
    b_phone = cfgs.get("agent.brand.phone", "").strip()
    BRAND_NAME = b_name if b_name else "ALIJAYA NET"
    BRAND_PHONE = b_phone if b_phone else "081947215703"

def is_valid_token(val):
    if not val:
        return False
    if "MASUKKAN_" in val:
        return False
    return True

def parse_admin_chat_ids(val):
    if not val or not is_valid_token(val):
        return []
    cleaned = val.replace(";", ",").replace("\n", ",")
    return [x.strip() for x in cleaned.split(",") if x.strip()]

def is_authorized(sender_id, admin_ids):
    if not admin_ids:
        return False
    return str(sender_id) in admin_ids

# ==============================================================================
# KEYBOARD MARKUPS
# ==============================================================================

def get_main_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "🔍 Cek Modem"}, {"text": "⚠️ Cek Redaman Kritis"}],
            [{"text": "👥 Daftar Klien WiFi"}, {"text": "🆕 Modem Belum Setting"}],
            [{"text": "🌐 Tambah / Set WAN"}, {"text": "🔄 Reboot Modem"}],
            [{"text": "📶 Ubah WiFi / Sandi"}, {"text": "📊 Status Server STB"}],
            [{"text": "❓ Bantuan / Help"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def get_device_inline_keyboard(pppoe_user, dev_id=None, wifi_enabled=True):
    target = pppoe_user if pppoe_user else dev_id
    wifi_toggle_text = "🚫 Matikan WiFi" if wifi_enabled else "📶 Hidupkan WiFi"
    wifi_toggle_action = f"wifioff:{target}" if wifi_enabled else f"wifion:{target}"
    
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 Reboot Modem", "callback_data": f"reboot:{target}"},
                {"text": "⚡ Refresh Data", "callback_data": f"refresh:{target}"}
            ],
            [
                {"text": "👥 Cek Klien HP", "callback_data": f"klien:{target}"},
                {"text": "🌐 Set WAN PPPoE", "callback_data": f"prompt_wan:{target}"}
            ],
            [
                {"text": "📶 Ganti SSID", "callback_data": f"prompt_ssid:{target}"},
                {"text": "🔑 Ganti Sandi", "callback_data": f"prompt_pass:{target}"}
            ],
            [
                {"text": wifi_toggle_text, "callback_data": wifi_toggle_action},
                {"text": "⚠️ Factory Reset", "callback_data": f"prompt_fr:{target}"}
            ]
        ]
    }

# ==============================================================================
# GENIEACS CORE OPERATIONS
# ==============================================================================


def normalize_phone(phone_str):
    if not phone_str:
        return ""
    digits = re.sub(r"\D", "", str(phone_str))
    if digits.startswith("62"):
        return "0" + digits[2:]
    return digits

def get_phone_variations(phone_str):
    if not phone_str:
        return []
    digits = re.sub(r"\D", "", str(phone_str))
    if len(digits) < 8:
        return [str(phone_str).strip()]
    if digits.startswith("62"):
        local = "0" + digits[2:]
        intl = digits
    elif digits.startswith("0"):
        local = digits
        intl = "62" + digits[1:]
    else:
        local = "0" + digits
        intl = "62" + digits
    return list(set([local, intl, f"+{intl}", f"wa:{local}", f"wa:{intl}"]))

def find_device_by_phone(phone_str):
    if not phone_str:
        return None
    db = get_db()
    if db is None:
        return None
    variations = get_phone_variations(phone_str)
    digits = re.sub(r"\D", "", str(phone_str))
    local = "0" + digits[2:] if digits.startswith("62") else digits
    intl = "62" + digits[1:] if digits.startswith("0") else digits
    plain = digits[1:] if digits.startswith("0") else (digits[2:] if digits.startswith("62") else digits)

    # 1. Prioritas Utama: Cek di db.device_locations (Data No. HP Pelanggan dari Peta GenieACS)
    loc_filters = [
        {"phone": {"$in": variations}},
        {"phone": local},
        {"phone": intl},
        {"phone": digits}
    ]
    if len(plain) >= 7:
        loc_filters.append({"phone": {"$regex": re.escape(plain)}})

    try:
        loc = db.device_locations.find_one({"$or": loc_filters})
        if loc and loc.get("_id"):
            dev = find_device(loc.get("_id"))
            if dev:
                if loc.get("name"):
                    dev["_custom_customer_name"] = loc.get("name")
                return dev
    except Exception as e:
        logger.warning(f"Error querying device_locations by phone: {e}")

    # 2. Prioritas Kedua: Cek tags pada db.devices
    dev = db.devices.find_one({
        "$or": [
            {"_tags": {"$in": variations}},
            {"tags": {"$in": variations}},
            {"_tags": {"$regex": local}},
            {"tags": {"$regex": local}}
        ]
    })
    return dev

def add_device_tag(dev_id, tag_str):
    clean_tag = tag_str.strip()
    db = get_db()
    if db is not None:
        try:
            db.devices.update_one({"_id": dev_id}, {"$addToSet": {"_tags": clean_tag}})
        except Exception:
            pass
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tags/{quote(clean_tag)}"
        r = requests.post(url, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def remove_device_tag(dev_id, tag_str):
    clean_tag = tag_str.strip()
    db = get_db()
    if db is not None:
        try:
            db.devices.update_one({"_id": dev_id}, {"$pull": {"_tags": clean_tag}})
        except Exception:
            pass
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tags/{quote(clean_tag)}"
        r = requests.delete(url, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def get_device_pppoe_username(dev):
    if not dev:
        return "Unknown"
    vp = dev.get("VirtualParameters", {})
    pppoe = vp.get("pppoeUsername", {}).get("_value")
    if pppoe and pppoe not in ["0", "undefined", "null"]:
        return str(pppoe).strip()
    wandev = dev.get("InternetGatewayDevice", {}).get("WANDevice", {})
    for wk in wandev:
        if wk.startswith("_"): continue
        wcds = wandev[wk].get("WANConnectionDevice", {})
        for ck in wcds:
            if ck.startswith("_"): continue
            ppps = wcds[ck].get("WANPPPConnection", {})
            for pk in ppps:
                if pk.startswith("_"): continue
                u = ppps[pk].get("Username", {}).get("_value")
                if u:
                    return str(u).strip()
    return dev.get("_deviceId", {}).get("_SerialNumber") or dev.get("_id", "Unknown")

def get_datetime_diff_seconds(dt):
    if not dt:
        return 999999999
    try:
        from datetime import timezone
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            dt_ts = dt.timestamp()
        else:
            dt_ts = dt.replace(tzinfo=timezone.utc).timestamp()
        return max(0, time.time() - dt_ts)
    except Exception:
        return 999999999

def get_customer_friendly_summary(dev):
    if not dev:
        return "❌ Perangkat Anda tidak ditemukan."
    vp = dev.get("VirtualParameters", {})
    igd = dev.get("InternetGatewayDevice", {})
    
    pppoe = get_device_pppoe_username(dev)
    
    # Redaman
    rx = vp.get("RXPower", {}).get("_value") or "-"
    rx_badge = ""
    if rx != "-":
        try:
            rx_val = float(str(rx).replace("dBm", "").strip())
            if rx_val >= -24.0:
                rx_badge = "(Sinyal Bagus 🟢)"
            elif rx_val >= -27.0:
                rx_badge = "(Normal 🟡)"
            else:
                rx_badge = "(Lemah / Redaman Tinggi 🔴)"
        except Exception:
            pass
        if not str(rx).endswith("dBm"):
            rx = f"{rx} dBm"

    uptime = vp.get("getdeviceuptime", {}).get("_value") or vp.get("uptimeDevice", {}).get("_value") or "-"
    
    wlan1 = igd.get("LANDevice", {}).get("1", {}).get("WLANConfiguration", {}).get("1", {})
    ssid = wlan1.get("SSID", {}).get("_value") or vp.get("WlanSSID", {}).get("_value") or "-"
    wifi_pass = (
        wlan1.get("KeyPassphrase", {}).get("_value") or
        wlan1.get("PreSharedKey", {}).get("1", {}).get("KeyPassphrase", {}).get("_value") or
        vp.get("WlanPassword", {}).get("_value") or
        "(Tersimpan di Modem)"
    )
    
    clients = (
        wlan1.get("TotalAssociations", {}).get("_value") or
        vp.get("activedevices", {}).get("_value") or
        "0"
    )
    
    last_inform = dev.get("_lastInform")
    online_str = "Offline 🔴"
    if last_inform:
        diff_sec = get_datetime_diff_seconds(last_inform)
        if diff_sec < 600:
            online_str = "Online (Normal) 🟢"
        else:
            online_str = f"Offline ({int(diff_sec//60)} mnt lalu) 🔴"

    return (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  📶 *STATUS LAYANAN WIFI ANDA*\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"• *ID Pelanggan*   : `{pppoe}`\n"
        f"• *Status Koneksi* : {online_str}\n"
        f"• *Nama WiFi (SSID)*: `{ssid}`\n"
        f"• *Kata Sandi*     : `{wifi_pass}`\n"
        f"• *Kualitas Sinyal*: `{rx}` {rx_badge}\n"
        f"• *Perangkat Konek*: `{clients} HP/Laptop`\n"
        f"• *Waktu Aktif*    : `{uptime}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *Perintah Mandiri:*\n"
        f"• `wifi <nama_baru> <sandi_baru>` ➔ Ganti nama & sandi\n"
        f"• `pass <sandi_baru>` ➔ Ganti sandi saja (min. 8 huruf/angka)\n"
        f"• `ssid <nama_baru>` ➔ Ganti nama WiFi saja\n"
        f"• `reboot` ➔ Restart modem jika koneksi berat"
    )

def find_device(query_str):
    db = get_db()
    if db is None:
        return None
    q = query_str.strip()
    reg = {"$regex": q, "$options": "i"}

    dev = db.devices.find_one({
        "$or": [
            {"_tags": reg},
            {"tags": reg},
            {"VirtualParameters.pppoeUsername._value": reg},
            {"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.Username._value": reg},
            {"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.2.WANPPPConnection.1.Username._value": reg},
            {"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.WANPPPConnection.1.Username._value": reg},
            {"VirtualParameters.WlanSSID._value": reg},
            {"InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID._value": reg},
            {"_id": reg},
            {"_deviceId._SerialNumber": reg},
            {"DeviceID.SerialNumber._value": reg},
            {"VirtualParameters.pppoeIP._value": q},
            {"VirtualParameters.MacAddress._value": reg},
            {"VirtualParameters.PonMac._value": reg},
            {"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.ExternalIPAddress._value": q}
        ]
    })
    return dev

def get_device_summary(dev):
    if not dev:
        return None, "❌ Perangkat modem tidak ditemukan. Pastikan Username PPPoE atau Serial Number benar.", True
    
    dev_id = dev.get("_id", "Unknown")
    vp = dev.get("VirtualParameters", {})
    igd = dev.get("InternetGatewayDevice", {})
    did = dev.get("_deviceId", {})
    
    # 1. Identitas PPPoE / Nama Pelanggan
    pppoe = vp.get("pppoeUsername", {}).get("_value")
    if not pppoe:
        wandev = igd.get("WANDevice", {})
        for wk in wandev:
            if wk.startswith("_"): continue
            wcds = wandev[wk].get("WANConnectionDevice", {})
            for ck in wcds:
                if ck.startswith("_"): continue
                ppps = wcds[ck].get("WANPPPConnection", {})
                for pk in ppps:
                    if pk.startswith("_"): continue
                    u = ppps[pk].get("Username", {}).get("_value")
                    if u:
                        pppoe = u
                        break
    
    has_pppoe = bool(pppoe and pppoe not in ["0", "undefined", "null"])
    display_user = pppoe if has_pppoe else "(Belum Terisi / ONT Baru)"
    
    # 2. Redaman & Sinyal Optik
    rx = vp.get("RXPower", {}).get("_value") or "-"
    rx_badge = ""
    if rx != "-":
        try:
            rx_val = float(str(rx).replace("dBm", "").strip())
            if rx_val >= -23.0:
                rx_badge = "(Sangat Bagus 🟢)"
            elif rx_val >= -26.0:
                rx_badge = "(Normal 🟡)"
            else:
                rx_badge = "(Kritis / Drop 🔴)"
        except Exception:
            pass
        if not str(rx).endswith("dBm"):
            rx = f"{rx} dBm"
        
    temp = vp.get("gettemp", {}).get("_value") or vp.get("temp", {}).get("_value") or "-"
    if temp != "-" and not str(temp).endswith("°C"):
        temp = f"{temp} °C"
        
    uptime = vp.get("getdeviceuptime", {}).get("_value") or vp.get("uptimeDevice", {}).get("_value") or "-"
    
    ip = vp.get("pppoeIP", {}).get("_value") or "-"
    if ip == "-":
        wandev = igd.get("WANDevice", {})
        for wk in wandev:
            if wk.startswith("_"): continue
            wcds = wandev[wk].get("WANConnectionDevice", {})
            for ck in wcds:
                if ck.startswith("_"): continue
                ppps = wcds[ck].get("WANPPPConnection", {})
                for pk in ppps:
                    if pk.startswith("_"): continue
                    ext_ip = ppps[pk].get("ExternalIPAddress", {}).get("_value")
                    if ext_ip and ext_ip != "0.0.0.0":
                        ip = ext_ip
                        break
    
    wlan1 = igd.get("LANDevice", {}).get("1", {}).get("WLANConfiguration", {}).get("1", {})
    ssid = wlan1.get("SSID", {}).get("_value") or vp.get("WlanSSID", {}).get("_value") or "-"
    wifi_pass = (
        wlan1.get("KeyPassphrase", {}).get("_value") or
        wlan1.get("PreSharedKey", {}).get("1", {}).get("KeyPassphrase", {}).get("_value") or
        vp.get("WlanPassword", {}).get("_value") or
        "(Tersimpan Aman di Modem)"
    )
    
    wifi_enable_val = str(wlan1.get("Enable", {}).get("_value", "true")).lower()
    wifi_is_on = wifi_enable_val not in ["false", "0"]
    
    clients = (
        wlan1.get("TotalAssociations", {}).get("_value") or
        vp.get("activedevices", {}).get("_value") or
        "0"
    )
    
    last_inform = dev.get("_lastInform")
    online_str = "Offline 🔴"
    if last_inform:
        diff_sec = get_datetime_diff_seconds(last_inform)
        if diff_sec < 600:
            online_str = "Online (Aktif) 🟢"
        else:
            online_str = f"Offline ({int(diff_sec//60)} mnt lalu) 🔴"
            
    mfr = did.get("_Manufacturer") or dev.get("DeviceID", {}).get("Manufacturer", {}).get("_value") or "-"
    model = did.get("_ProductClass") or dev.get("DeviceID", {}).get("ProductClass", {}).get("_value") or "-"
    sn = did.get("_SerialNumber") or dev.get("DeviceID", {}).get("SerialNumber", {}).get("_value") or dev_id
    mac = vp.get("MacAddress", {}).get("_value") or vp.get("PonMac", {}).get("_value") or "-"
    
    res = (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  👤 *PELANGGAN : {display_user.upper()}*\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"• *Akun PPPoE*    : `{display_user}`\n"
        f"• *Status ONT*    : {online_str}\n"
        f"• *Redaman (RX)*  : `{rx}` {rx_badge}\n"
        f"• *Suhu Transceiver*: `{temp}`\n"
        f"• *IP WAN PPPoE*  : `{ip}`\n"
        f"• *Uptime Modem*  : `{uptime}`\n"
        f"• *Nama WiFi*     : `{ssid}` ({'Radio ON 🟢' if wifi_is_on else 'Radio OFF 🔴'})\n"
        f"• *Sandi WiFi*    : `{wifi_pass}`\n"
        f"• *User Konek*    : `{clients} perangkat`\n"
        f"• *Model Hardware*: {mfr} {model}\n"
        f"• *Serial Number* : `{sn}`\n"
        f"• *MAC Address*   : `{mac}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 *{BRAND_NAME} TR-069 Management*"
    )
    return display_user, res, wifi_is_on

def get_device_clients(dev):
    if not dev:
        return "❌ Perangkat modem tidak ditemukan."
    
    dev_id = dev.get("_id", "Unknown")
    vp = dev.get("VirtualParameters", {})
    pppoe = vp.get("pppoeUsername", {}).get("_value") or dev_id
    
    igd = dev.get("InternetGatewayDevice", {})
    lan = igd.get("LANDevice", {}).get("1", {})
    hosts = lan.get("Hosts", {}).get("Host", {})
    
    client_list = []
    for k, h in hosts.items():
        if k.startswith("_"): continue
        ip = h.get("IPAddress", {}).get("_value")
        mac = h.get("MACAddress", {}).get("_value")
        name = h.get("HostName", {}).get("_value") or "Perangkat WiFi"
        active = str(h.get("Active", {}).get("_value", "true")).lower()
        if ip or mac:
            is_act = active not in ["false", "0"]
            client_list.append({
                "name": name,
                "ip": ip or "-",
                "mac": mac or "-",
                "active": is_act
            })
            
    if not client_list:
        return (
            f"👥 *DAFTAR PERANGKAT KLIEN TERKONEKSI*\n"
            f"👤 *Pelanggan*: `{pppoe}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Tidak ada data klien yang tersimpan di memori TR-069 saat ini.\n"
            f"Ketik `/refresh {pppoe}` untuk memperbarui data langsung dari modem."
        )
        
    lines = [
        f"👥 *DAFTAR PERANGKAT KLIEN TERKONEKSI*",
        f"👤 *Pelanggan*: `{pppoe.upper()}`",
        f"━━━━━━━━━━━━━━━━━━━━"
    ]
    for idx, c in enumerate(client_list[:15], start=1):
        status_icon = "🟢" if c["active"] else "⚪"
        lines.append(f"{idx}. 📱 *{c['name']}* {status_icon}")
        lines.append(f"   • IP: `{c['ip']}` | MAC: `{c['mac']}`")
        
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Total Terdeteksi: *{len(client_list)} perangkat*")
    return "\n".join(lines)

def get_bad_rx_summary():
    db = get_db()
    if db is None:
        return "❌ Gagal membuka database MongoDB."
        
    bad_list = []
    cursor = db.devices.find({"VirtualParameters.RXPower": {"$exists": True}})
    
    for dev in cursor:
        vp = dev.get("VirtualParameters", {})
        did = dev.get("_deviceId", {})
        dev_id = dev.get("_id", "")
        
        pppoe = vp.get("pppoeUsername", {}).get("_value")
        if not pppoe or pppoe in ["0", "undefined"]:
            pppoe = did.get("_SerialNumber") or dev_id
            
        rx_raw = vp.get("RXPower", {}).get("_value")
        try:
            rx_val = float(str(rx_raw).replace("dBm", "").strip())
            if rx_val < -26.0 or rx_val > -5.0:
                mfr = did.get("_Manufacturer", "")
                model = did.get("_ProductClass", "")
                bad_list.append({
                    "pppoe": pppoe,
                    "rx": rx_val,
                    "model": f"{mfr} {model}".strip()
                })
        except Exception:
            pass
            
    bad_list.sort(key=lambda x: x["rx"])
    
    if not bad_list:
        return "🎉 *SEMUA REDAMAN NORMAL!*\nTidak ditemukan modem dengan redaman kritis (seluruhnya di atas -26 dBm)."
        
    lines = [
        "⚠️ *DAFTAR MODEM REDAMAN KRITIS / DROP (< -26 dBm)*",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    for idx, b in enumerate(bad_list[:20], start=1):
        tag = "🔴 Kritis" if b["rx"] < -28.0 else "🟡 Waspada"
        lines.append(f"{idx}. 👤 *{b['pppoe']}* : `{b['rx']} dBm` ({tag})")
        if b["model"]:
            lines.append(f"   • Perangkat: {b['model']}")
            
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Total bermasalah: *{len(bad_list)} pelanggan*.")
    lines.append("👉 _Ketik `/cek <username>` untuk melihat rincian pelanggan._")
    return "\n".join(lines)

def get_unconfigured_onts():
    db = get_db()
    if db is None:
        return "❌ Gagal membuka database MongoDB."
        
    cursor = db.devices.find({
        "$or": [
            {"VirtualParameters.pppoeUsername": {"$exists": False}},
            {"VirtualParameters.pppoeUsername._value": {"$in": ["", None, "0", "undefined"]}}
        ]
    })
    
    unconf_list = []
    for d in cursor:
        dev_id = d.get("_id", "")
        if "DISCOVERYSERVICE" in dev_id.upper():
            continue
        did = d.get("_deviceId", {})
        sn = did.get("_SerialNumber") or d.get("DeviceID", {}).get("SerialNumber", {}).get("_value") or dev_id
        mfr = did.get("_Manufacturer") or d.get("DeviceID", {}).get("Manufacturer", {}).get("_value") or "-"
        model = did.get("_ProductClass") or d.get("DeviceID", {}).get("ProductClass", {}).get("_value") or "-"
        
        last_inform = d.get("_lastInform")
        ago_str = "-"
        if last_inform:
            ago_str = f"{int(get_datetime_diff_seconds(last_inform) // 60)} mnt lalu"
            
        unconf_list.append({
            "sn": sn,
            "hw": f"{mfr} {model}".strip(),
            "ago": ago_str
        })
        
    if not unconf_list:
        return "✅ *Tidak ada ONT Baru*: Semua modem yang terhubung sudah memiliki konfigurasi PPPoE."
        
    lines = [
        "🆕 *DAFTAR MODEM BARU BELUM DISETTING PPPoE*",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    for idx, u in enumerate(unconf_list[:15], start=1):
        lines.append(f"{idx}. 📡 *SN*: `{u['sn']}` ({u['hw']})")
        lines.append(f"   • Terakhir Kontak: {u['ago']}")
        lines.append(f"   • Format: `/addwan {u['sn']} <user> <pass>`")
        
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Total ONT baru: *{len(unconf_list)} perangkat*.")
    return "\n".join(lines)

def set_wifi_credentials(dev, new_ssid=None, new_password=None):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    
    param_values = []
    if new_ssid:
        param_values.append(["InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID", new_ssid, "xsd:string"])
    if new_password:
        param_values.append(["InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.KeyPassphrase", new_password, "xsd:string"])
        param_values.append(["InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.PreSharedKey.1.KeyPassphrase", new_password, "xsd:string"])
        param_values.append(["VirtualParameters.WlanPassword", new_password, "xsd:string"])
        
    if not param_values:
        return False, "Tidak ada data SSID atau Sandi yang diubah."
        
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {
            "name": "setParameterValues",
            "parameterValues": param_values
        }
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            return True, f"Berhasil mengirim instruksi ganti WiFi ke modem `{dev_id}`."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except requests.exceptions.Timeout:
        return True, f"Instruksi ganti WiFi telah dikirim ke antrean modem `{dev_id}`."
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def set_wifi_power(dev, enable=True):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    val_str = "true" if enable else "false"
    
    param_values = [
        ["InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.Enable", val_str, "xsd:boolean"],
        ["InternetGatewayDevice.LANDevice.1.WLANConfiguration.2.Enable", val_str, "xsd:boolean"]
    ]
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {
            "name": "setParameterValues",
            "parameterValues": param_values
        }
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            action_txt = "diaktifkan kembali 🟢" if enable else "dimatikan 🔴"
            return True, f"Radio pemancar WiFi modem `{dev_id}` berhasil {action_txt}."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except requests.exceptions.Timeout:
        action_txt = "diaktifkan 🟢" if enable else "dimatikan 🔴"
        return True, f"Instruksi radio WiFi {action_txt} telah dikirim ke antrean modem `{dev_id}`."
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def add_or_set_wan_pppoe(dev, pppoe_user, pppoe_pass, vlan_id=None):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    dev_id_info = dev.get("_deviceId", {})
    mfg = str(dev_id_info.get("_Manufacturer", "")).upper()
    oui = str(dev_id_info.get("_OUI", "")).upper()
    prod_class = str(dev_id_info.get("_ProductClass", "")).upper()

    igd = dev.get("InternetGatewayDevice", {})
    wandev = igd.get("WANDevice", {})

    target_path = None
    target_node = None
    best_match_score = -1

    for wk in wandev:
        if wk.startswith("_"): continue
        wcds = wandev[wk].get("WANConnectionDevice", {})
        for ck in wcds:
            if ck.startswith("_"): continue
            ppps = wcds[ck].get("WANPPPConnection", {})
            for pk in ppps:
                if pk.startswith("_"): continue
                p = ppps[pk]
                name = str(p.get("Name", {}).get("_value", "")).upper()
                cur_user = str(p.get("Username", {}).get("_value", ""))
                
                score = 0
                if cur_user == pppoe_user and pppoe_user:
                    score = 100
                elif "INTERNET" in name:
                    score = 80
                elif cur_user != "":
                    score = 50
                elif cur_user == "":
                    score = 30
                
                if score > best_match_score:
                    best_match_score = score
                    target_path = f"InternetGatewayDevice.WANDevice.{wk}.WANConnectionDevice.{ck}.WANPPPConnection.{pk}"
                    target_node = p

    if not target_path:
        base_obj = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection."
        add_url = f"{NBI_URL}/devices/{quote(dev_id, safe='')}/tasks"
        add_body = {
            "name": "addObject",
            "objectName": base_obj
        }
        try:
            requests.post(add_url, json=add_body, timeout=5)
        except Exception:
            pass
        target_path = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1"

    param_values = [
        [f"{target_path}.Enable", "true", "xsd:boolean"],
        [f"{target_path}.Username", pppoe_user, "xsd:string"],
        [f"{target_path}.Password", pppoe_pass, "xsd:string"],
        [f"{target_path}.ConnectionType", "IP_Routed", "xsd:string"],
        [f"{target_path}.NATEnabled", "true", "xsd:boolean"]
    ]

    # Handle VLAN cleanly and accurately per vendor (prevents TR-069 Fault 9005)
    if vlan_id is not None and str(vlan_id).strip() not in ("", "-", "0", "None"):
        v_str = str(vlan_id).strip()
        detected_vlan_param = None
        if target_node:
            for vk in ["X_CT-COM_VlanID", "X_CMCC_VLANIDMark", "X_HW_VLAN", "X_ZTE-COM_VlanID", "VLANID", "X_BROADCOM_COM_VLANID"]:
                if vk in target_node:
                    detected_vlan_param = vk
                    break
        
        if detected_vlan_param:
            param_values.append([f"{target_path}.{detected_vlan_param}", v_str, "xsd:unsignedInt"])
            if detected_vlan_param == "X_CMCC_VLANIDMark":
                param_values.append([f"{target_path}.X_CMCC_VLANMode", "1", "xsd:unsignedInt"])
            elif detected_vlan_param == "X_CT-COM_VlanID":
                param_values.append([f"{target_path}.X_CT-COM_Mode", "1", "xsd:unsignedInt"])
        elif not target_node or len(target_node) == 0:
            # Fallback only when target_node parameters are unknown / newly created
            if "HUAWEI" in mfg or "00259E" in oui:
                param_values.append([f"{target_path}.X_HW_VLAN", v_str, "xsd:unsignedInt"])
            elif "ZTE" in mfg or "ZICG" in mfg:
                param_values.append([f"{target_path}.X_CMCC_VLANIDMark", v_str, "xsd:unsignedInt"])
                param_values.append([f"{target_path}.X_CMCC_VLANMode", "1", "xsd:unsignedInt"])
            elif "CIOT" in mfg or "GM220" in prod_class or "M63X" in prod_class or "RTEG" in mfg:
                param_values.append([f"{target_path}.X_CT-COM_VlanID", v_str, "xsd:unsignedInt"])
                param_values.append([f"{target_path}.X_CT-COM_Mode", "1", "xsd:unsignedInt"])
            else:
                param_values.append([f"{target_path}.VLANID", v_str, "xsd:unsignedInt"])

    url_cr = f"{NBI_URL}/devices/{quote(dev_id, safe='')}/tasks?connection_request"
    url_queue = f"{NBI_URL}/devices/{quote(dev_id, safe='')}/tasks"
    body = {
        "name": "setParameterValues",
        "parameterValues": param_values
    }

    success = False
    try:
        r = requests.post(url_cr, json=body, timeout=4)
        if r.status_code in [200, 202]:
            success = True
    except Exception:
        pass

    if not success:
        try:
            r = requests.post(url_queue, json=body, timeout=5)
            if r.status_code in [200, 202]:
                success = True
        except Exception as e:
            logger.error(f"Failed to send setParameterValues to NBI: {e}")
            return False, f"Gagal menghubungi GenieACS NBI: {e}"

    if success:
        vlan_text = f"\n• *VLAN ID*: `{vlan_id}`" if (vlan_id and str(vlan_id) not in ("", "0", "-")) else "\n• *VLAN*: `Untagged`"
        return True, (
            f"✅ *Berhasil Menerapkan Konfigurasi WAN PPPoE!*\n"
            f"• *Modem*: `{dev_id}`\n"
            f"• *Jalur*: `{target_path}`\n"
            f"• *Username PPPoE*: `{pppoe_user}`\n"
            f"• *Password*: `{'*' * len(pppoe_pass)}`"
            f"{vlan_text}\n"
            f"• *Status*: Tugas TR-069 tersimpan dan akan segera dieksekusi ke modem."
        )
    return False, "Gagal mengirim tugas TR-069 ke GenieACS NBI."

def set_superadmin_password(dev, new_pass):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    
    param_values = [
        ["InternetGatewayDevice.UserInterface.Password", new_pass, "xsd:string"],
        ["InternetGatewayDevice.UserInterface.X_ZTE-COM_AdminAccount.Password", new_pass, "xsd:string"],
        ["InternetGatewayDevice.X_CT-COM_TeleComAccount.Password", new_pass, "xsd:string"],
        ["InternetGatewayDevice.UserInterface.X_HW_AdminAccount.Password", new_pass, "xsd:string"]
    ]
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {
            "name": "setParameterValues",
            "parameterValues": param_values
        }
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            return True, f"Perintah ubah sandi SuperAdmin Web ONT berhasil dikirim ke `{dev_id}`."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def ping_diagnostics_task(dev, host="8.8.8.8"):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    param_values = [
        ["InternetGatewayDevice.IPPingDiagnostics.DiagnosticsState", "Requested", "xsd:string"],
        ["InternetGatewayDevice.IPPingDiagnostics.Host", host, "xsd:string"],
        ["InternetGatewayDevice.IPPingDiagnostics.NumberOfRepetitions", "3", "xsd:unsignedInt"]
    ]
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {
            "name": "setParameterValues",
            "parameterValues": param_values
        }
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            return True, f"Perintah Ping Diagnostics ke `{host}` berhasil dikirim ke modem `{dev_id}` via TR-069."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except requests.exceptions.Timeout:
        return True, f"Perintah Ping Diagnostics ke `{host}` berhasil dikirim ke antrean modem `{dev_id}`."
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def factory_reset_device(dev):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {"name": "factoryReset"}
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            return True, f"Perintah FACTORY RESET berhasil dikirim ke modem `{dev_id}`. Modem akan kembali ke setelan pabrik."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def reboot_device_task(dev):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {"name": "reboot"}
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            return True, f"Perintah Restart berhasil dikirim ke modem `{dev_id}`."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except requests.exceptions.Timeout:
        return True, f"Perintah Restart telah dikirim ke antrean modem `{dev_id}`."
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def refresh_device_task(dev):
    if not dev:
        return False, "Modem pelanggan tidak ditemukan."
    dev_id = dev.get("_id")
    try:
        url = f"{NBI_URL}/devices/{quote(dev_id)}/tasks?connection_request"
        body = {"name": "refreshObject", "objectName": ""}
        r = requests.post(url, json=body, timeout=10)
        if r.status_code in [200, 202]:
            return True, f"Modem `{dev_id}` berhasil di-summon/refresh."
        else:
            return False, f"GenieACS merespon HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, f"Gagal menghubungi GenieACS NBI: {e}"

def get_server_stats():
    try:
        df_out = subprocess.check_output("df -h / | tail -n 1", shell=True).decode().split()
        disk_used = f"{df_out[2]} / {df_out[1]} ({df_out[4]})"
        free_out = subprocess.check_output("free -m | grep Mem:", shell=True).decode().split()
        ram_used = f"{free_out[2]} MB / {free_out[1]} MB"
        load_out = subprocess.check_output("uptime", shell=True).decode().strip()
        temp_out = "N/A"
        try:
            temp_raw = subprocess.check_output("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null", shell=True).decode().strip()
            if temp_raw:
                temp_out = f"{float(temp_raw)/1000:.1f} °C"
        except Exception:
            pass

        return (
            "📊 *STATUS SERVER STB ARMBIAN*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"• *RAM Terpakai*: `{ram_used}`\n"
            f"• *Penyimpanan (eMMC/SD)*: `{disk_used}`\n"
            f"• *Suhu CPU STB*: `{temp_out}`\n"
            f"• *Uptime Server*: `{load_out.split('up ')[1].split(',')[0] if 'up ' in load_out else '-'}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🟢 *GenieACS TR-069 & MongoDB: Normal*"
        )
    except Exception as e:
        return f"Gagal membaca status server: {e}"

# ==============================================================================
# GEMINI AI ASSISTANT FALLBACK
# ==============================================================================

def ask_gemini_ai(gemini_key, model_name, user_prompt, sender_id):
    if not is_valid_token(gemini_key):
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    system_instruction = (
        f"Anda adalah Asisten AI Resmi dari {BRAND_NAME} untuk Manajemen TR-069 GenieACS RT/RW Net.\n"
        f"Kontak CS/WhatsApp: {BRAND_PHONE}.\n"
        "Bantu teknisi lapangan menjawab pertanyaan teknis secara singkat, ramah, dan profesional seputar "
        "modem ONT (ZTE, Huawei, Fiberhome, GM220-S), redaman optik (standar bagus -14 s/d -24 dBm), "
        "koneksi PPPoE, WiFi, atau cara menggunakan perintah bot ini (/cek, /redaman, /ontbaru, /klien, /addwan, /wifioff, /wifion, /reboot)."
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\nPertanyaan teknisi: {user_prompt}"}
                ]
            }
        ]
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        logger.warning(f"Gemini API request failed: {e}")
    return None

# ==============================================================================
# TELEGRAM API HELPERS
# ==============================================================================

def send_telegram(token, chat_id, text, parse_mode="Markdown", reply_markup=None):
    if not text or not str(text).strip():
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")

def answer_callback(token, callback_id, text, show_alert=False):
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_id, "text": text, "show_alert": show_alert}, timeout=8)
    except Exception as e:
        logger.error(f"Failed to answer callback: {e}")

def register_bot_commands(token):
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    commands = [
        {"command": "menu", "description": "Tampilkan Menu Tombol Cepat"},
        {"command": "cek", "description": "Cek redaman & status: /cek <user_atau_sn>"},
        {"command": "redaman", "description": "Audit modem redaman kritis / drop"},
        {"command": "ontbaru", "description": "Cek modem baru belum disetting PPPoE"},
        {"command": "klien", "description": "Cek HP/laptop terhubung: /klien <user>"},
        {"command": "addwan", "description": "Tambah/Set WAN: /addwan <sn> <user> <pass> [vlan]"},
        {"command": "wifioff", "description": "Matikan pemancar WiFi: /wifioff <user>"},
        {"command": "wifion", "description": "Hidupkan pemancar WiFi: /wifion <user>"},
        {"command": "ssid", "description": "Ganti nama WiFi saja: /ssid <user> <nama>"},
        {"command": "pass", "description": "Ganti sandi WiFi saja: /pass <user> <sandi>"},
        {"command": "wifi", "description": "Ganti SSID & Sandi: /wifi <user> <ssid> <sandi>"},
        {"command": "ping", "description": "Diagnostik Ping TR-069: /ping <user> [host]"},
        {"command": "superadmin", "description": "Ganti sandi admin web ONT: /superadmin <user> <pass>"},
        {"command": "reboot", "description": "Restart modem pelanggan: /reboot <user>"},
        {"command": "factoryreset", "description": "Reset modem ke setelan pabrik: /factoryreset <user>"},
        {"command": "server", "description": "Cek status CPU, RAM & Suhu STB"},
        {"command": "help", "description": "Panduan lengkap penggunaan bot"}
    ]
    try:
        requests.post(url, json={"commands": commands}, timeout=8)
        logger.info("Bot commands registered successfully with Telegram.")
    except Exception as e:
        logger.warning(f"Could not register bot commands: {e}")

# ==============================================================================
# MESSAGE & CALLBACK HANDLERS
# ==============================================================================

def handle_callback_query(token, sender_id, cb_data, callback_id):
    logger.info(f"Handling callback: {cb_data} from {sender_id}")
    parts = cb_data.split(":", 1)
    act = parts[0]
    target = parts[1] if len(parts) > 1 else ""

    if act == "reboot" and target:
        dev = find_device(target)
        if not dev:
            answer_callback(token, callback_id, f"Modem {target} tidak ditemukan!", show_alert=True)
            return
        ok, msg = reboot_device_task(dev)
        answer_callback(token, callback_id, "Perintah Reboot terkirim!", show_alert=False)
        send_telegram(token, sender_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if act == "refresh" and target:
        dev = find_device(target)
        if not dev:
            answer_callback(token, callback_id, f"Modem {target} tidak ditemukan!", show_alert=True)
            return
        refresh_device_task(dev)
        answer_callback(token, callback_id, "Memperbarui data dari modem...", show_alert=False)
        time.sleep(1.5)
        fresh_dev = find_device(target)
        pppoe, summary, wifi_on = get_device_summary(fresh_dev)
        kb = get_device_inline_keyboard(pppoe, fresh_dev.get("_id"), wifi_on)
        send_telegram(token, sender_id, summary, reply_markup=kb)
        return

    if act == "klien" and target:
        dev = find_device(target)
        if not dev:
            answer_callback(token, callback_id, f"Modem {target} tidak ditemukan!", show_alert=True)
            return
        answer_callback(token, callback_id, "Mengambil daftar klien...", show_alert=False)
        msg = get_device_clients(dev)
        send_telegram(token, sender_id, msg)
        return

    if act == "wifioff" and target:
        dev = find_device(target)
        if not dev:
            answer_callback(token, callback_id, f"Modem {target} tidak ditemukan!", show_alert=True)
            return
        ok, msg = set_wifi_power(dev, enable=False)
        answer_callback(token, callback_id, "WiFi dinonaktifkan!", show_alert=False)
        send_telegram(token, sender_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if act == "wifion" and target:
        dev = find_device(target)
        if not dev:
            answer_callback(token, callback_id, f"Modem {target} tidak ditemukan!", show_alert=True)
            return
        ok, msg = set_wifi_power(dev, enable=True)
        answer_callback(token, callback_id, "WiFi diaktifkan!", show_alert=False)
        send_telegram(token, sender_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if act == "prompt_fr" and target:
        answer_callback(token, callback_id, "Peringatan Reset Pabrik", show_alert=False)
        confirm_kb = {
            "inline_keyboard": [
                [
                    {"text": "⚠️ Ya, Reset Pabrik", "callback_data": f"do_fr:{target}"},
                    {"text": "❌ Batal", "callback_data": "cancel_fr"}
                ]
            ]
        }
        send_telegram(token, sender_id, (
            f"⚠️ *KONFIRMASI FACTORY RESET*\n"
            f"Apakah Anda yakin ingin mereset modem pelanggan `{target}` ke setelan pabrik?\n"
            f"_Seluruh konfigurasi WAN, WiFi, dan sandi akan kembali ke standar bawaan pabrik._"
        ), reply_markup=confirm_kb)
        return

    if act == "do_fr" and target:
        dev = find_device(target)
        if not dev:
            answer_callback(token, callback_id, f"Modem {target} tidak ditemukan!", show_alert=True)
            return
        ok, msg = factory_reset_device(dev)
        answer_callback(token, callback_id, "Sinyal Reset Terkirim", show_alert=False)
        send_telegram(token, sender_id, f"{'✅' if ok else '❌'} {msg}")
        return

    if act == "cancel_fr":
        answer_callback(token, callback_id, "Dibatalkan", show_alert=False)
        send_telegram(token, sender_id, "✅ Operasi Factory Reset dibatalkan.")
        return

    if act == "prompt_ssid" and target:
        answer_callback(token, callback_id, "Ganti Nama WiFi", show_alert=False)
        USER_STATES[sender_id] = {"action": "wait_ssid", "target": target}
        send_telegram(token, sender_id, (
            f"📶 *Ganti Nama WiFi untuk Pelanggan: `{target}`*\n"
            f"Silakan ketik nama WiFi baru yang Anda inginkan:\n"
            f"_(Bisa langsung ketik namanya saja atau gunakan `/ssid {target} <nama_baru>`)_"
        ))
        return

    if act == "prompt_pass" and target:
        answer_callback(token, callback_id, "Ganti Sandi WiFi", show_alert=False)
        USER_STATES[sender_id] = {"action": "wait_pass", "target": target}
        send_telegram(token, sender_id, (
            f"🔑 *Ganti Sandi WiFi untuk Pelanggan: `{target}`*\n"
            f"Silakan ketik sandi WiFi baru (minimal 8 karakter):\n"
            f"_(Bisa langsung ketik sandinya saja atau gunakan `/pass {target} <sandi_baru>`)_"
        ))
        return

    if act == "prompt_wan" and target:
        answer_callback(token, callback_id, "Set WAN PPPoE", show_alert=False)
        USER_STATES[sender_id] = {"action": "wait_wan", "target": target}
        send_telegram(token, sender_id, (
            f"🌐 *Set Koneksi WAN PPPoE untuk: `{target}`*\n\n"
            f"Silakan ketik data dengan format:\n"
            f"`<user_pppoe> <password_pppoe> [vlan_id]`\n\n"
            f"_Contoh tanpa VLAN:_ `{target} 12345678`\n"
            f"_Contoh dengan VLAN:_ `{target} 12345678 100`"
        ))
        return

def process_agent_command(user_text, sender_id="admin", is_admin=True, gemini_key="", gemini_model="gemini-1.5-flash", registered_tag=None):
    raw = str(user_text or "").strip()
    if not raw:
        return ("⚠️ Pesan kosong.", None)

    txt = raw
    clean_txt = txt.lstrip("/!#").strip()

    # Exact check for quick button presses (matches emoji + text variations)
    btn_words = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_txt).strip().lower().split()
    btn_phrase = " ".join(btn_words)

    if btn_phrase in ("tambah set wan", "set wan"):
        wan_guide = (
            "🌐 *Tambah / Konfigurasi WAN PPPoE*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Silakan gunakan perintah dengan format:\n"
            "`addwan <sn_modem> <user_pppoe> <password_pppoe> [vlan_id]`\n\n"
            "📌 *Contoh Tanpa VLAN:*\n"
            "`addwan ZTEGC1234567 cucimotor 12345678`\n\n"
            "📌 *Contoh Dengan VLAN:*\n"
            "`addwan ZTEGC1234567 cucimotor 12345678 100`"
        )
        return (wan_guide, None)

    if btn_phrase in ("reboot modem", "restart modem"):
        return ("🔄 *Reboot Modem*: Silakan gunakan perintah:\n`reboot <username_pppoe/sn>`\n_Contoh:_ `reboot cucimotor`", None)

    if btn_phrase in ("ubah wifi sandi", "ubah wifi", "wifi sandi"):
        wifi_guide = (
            "📶 *Ubah WiFi / Sandi Pelanggan*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Silakan gunakan salah satu format perintah berikut:\n\n"
            "• *Ubah Nama & Sandi:* `wifi <user> <nama_wifi_baru> <sandi_baru>`\n"
            "  _Contoh:_ `wifi cucimotor Alijaya-Net 12345678`\n\n"
            "• *Ubah Nama WiFi Saja:* `ssid <user> <nama_wifi_baru>`\n"
            "  _Contoh:_ `ssid cucimotor Alijaya-Net`\n\n"
            "• *Ubah Sandi WiFi Saja:* `pass <user> <sandi_baru>`\n"
            "  _Contoh:_ `pass cucimotor 12345678`"
        )
        return (wifi_guide, None)

    if btn_phrase in ("status server stb", "status server", "status stb", "server stb"):
        return (get_server_stats(), get_main_menu_keyboard())

    if btn_phrase in ("daftar klien wifi", "daftar klien", "klien wifi", "cek klien"):
        return ("👥 *Daftar Klien Terhubung*: Silakan gunakan perintah:\n`klien <username_pppoe/sn>`\n_Contoh:_ `klien cucimotor`", None)

    if btn_phrase in ("cek modem", "info modem"):
        return ("🔍 *Cek Modem*: Silakan gunakan perintah:\n`cek <username_pppoe/sn>`\n_Contoh:_ `cek cucimotor`", None)

    if btn_phrase in ("cek redaman kritis", "cek redaman", "redaman kritis"):
        return (get_bad_rx_summary(), get_main_menu_keyboard())

    if btn_phrase in ("modem belum setting", "modem belum"):
        return (get_unconfigured_onts(), get_main_menu_keyboard())

    # Standard command parsing (stripping leading emojis/symbols)
    norm_txt = re.sub(r'^[^\w\s]+', '', clean_txt).strip()
    parts = norm_txt.split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    # Normalization of aliases for typed text
    if cmd in ["bantuan", "help", "menu", "start"] or btn_phrase in ("bantuan help", "bantuan", "help", "menu"):
        cmd = "menu"
        rest = ""
    elif cmd in ["server", "status"] and rest.lower() in ["", "server", "stb", "server stb"]:
        if is_admin:
            cmd = "server"
            rest = ""
        else:
            cmd = "cek"
            rest = ""
    elif cmd in ["restart", "reboot"]:
        cmd = "reboot"
        if rest.lower().startswith("modem"):
            rest = rest[5:].strip()
    elif cmd in ["cek", "status", "info", "sinyal", "koneksi"]:
        if rest.lower() in ["koneksi", "sinyal", "wifi", "modem", "status", "internet", "kuota"]:
            rest = ""
        cmd = "cek"
    elif cmd in ["ganti", "ubah"]:
        sub = rest.split(maxsplit=1)
        sub_type = sub[0].lower() if sub else ""
        sub_val = sub[1] if len(sub) > 1 else ""
        if sub_type in ["sandi", "password", "pass"]:
            cmd = "pass"
            rest = sub_val
        elif sub_type in ["wifi", "ssid", "nama"]:
            if sub_type == "nama" and sub_val.lower().startswith("wifi "):
                sub_val = sub_val[5:].strip()
            tokens = sub_val.split()
            if len(tokens) >= 2 and sub_type == "wifi":
                cmd = "wifi"
                rest = sub_val
            else:
                cmd = "ssid"
                rest = sub_val
    elif cmd == "klien" and rest.lower().startswith("wifi "):
        rest = rest[5:].strip()

    # 0. Resolusi Modem Pelanggan dari Tag Nomor WhatsApp Pengirim
    customer_dev = None
    if not is_admin:
        if registered_tag:
            customer_dev = find_device(registered_tag)
        if not customer_dev and sender_id:
            customer_dev = find_device_by_phone(sender_id)
            if customer_dev:
                registered_tag = customer_dev.get("_id")

    # 1. Menu & Help
    if cmd in ["menu", "start", "bantuan", "help"]:
        if is_admin:
            menu_text = (
                f"🤖 *{BRAND_NAME} - GenieACS TR-069 AI Bot*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📌 *Daftar Perintah Admin:*\n"
                "• `cek <user_pppoe/sn>` ➔ Status lengkap & redaman ONT\n"
                "• `redaman` ➔ Audit massal redaman kritis (< -26 dBm)\n"
                "• `ontbaru` ➔ Cek modem baru belum tersetting\n"
                "• `klien <user>` ➔ Daftar HP/laptop terhubung WiFi\n"
                "• `reboot <user>` ➔ Restart modem pelanggan\n"
                "• `wifion <user>` & `wifioff <user>` ➔ On/Off Radio WiFi\n"
                "• `wifi <user> <ssid> <sandi>` ➔ Ubah WiFi & Sandi\n"
                "• `ssid <user> <nama>` ➔ Ubah nama WiFi\n"
                "• `pass <user> <sandi>` ➔ Ubah sandi WiFi\n"
                "• `addwan <sn> <user> <pass> [vlan]` ➔ Tambah/Set WAN PPPoE\n"
                "• `superadmin <user> <sandi>` ➔ Ubah sandi web ONT\n"
                "• `ping <user> [host]` ➔ Uji ping TR-069 jarak jauh\n"
                "• `factoryreset <user>` ➔ Reset setelan pabrik\n"
                "• `tag <user> <wa>` ➔ Tautkan nomor WA pelanggan ke modem\n• `untag <user> <wa>` ➔ Hapus nomor WA pelanggan dari modem\n• `server` / `status` ➔ Status CPU, RAM, Suhu STB\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 *CS: {BRAND_NAME} ({BRAND_PHONE})*"
            )
            return (menu_text, get_main_menu_keyboard())
        else:
            if customer_dev:
                pppoe_user = get_device_pppoe_username(customer_dev)
                cust_name = customer_dev.get("_custom_customer_name") or ""
                greeting_header = f" Halo Kak *{cust_name}*!" if cust_name else " Halo!"
                cust_menu = (
                    f"👋 *{greeting_header} Layanan Mandiri WiFi {BRAND_NAME}*\n"
                    f"Modem Terdeteksi: *{pppoe_user}*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Fitur yang dapat Anda gunakan:\n"
                    "• `cek` ➔ Cek nama WiFi, kata sandi & status sinyal\n"
                    "• `wifi <nama_baru> <sandi_baru>` ➔ Ganti nama WiFi & sandi sekaligus\n"
                    "• `pass <sandi_baru>` ➔ Ganti sandi WiFi saja (min. 8 karakter)\n"
                    "• `ssid <nama_baru>` ➔ Ganti nama WiFi saja\n"
                    "• `reboot` ➔ Restart modem jika koneksi internet terasa lambat\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📞 *Butuh Bantuan Teknisi?* Hubungi CS di {BRAND_PHONE}"
                )
            else:
                clean_s = normalize_phone(sender_id)
                cust_menu = (
                    f"👋 *Halo! Selamat Datang di Layanan Otomatis {BRAND_NAME}*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"Nomor WhatsApp Anda (*{clean_s or sender_id}*) belum terdaftar pada modem mana pun.\n\n"
                    "📝 *Cara Menghubungkan:*\n"
                    "Ketik: `daftar <id_pppoe>`\n"
                    "_Contoh:_ `daftar cucimotor`\n\n"
                    f"Atau hubungi Layanan Bantuan / CS di {BRAND_PHONE}."
                )
            return (cust_menu, None)

    # 2. Cek Redaman Kritis
    if cmd in ["redaman", "los"]:
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin / Teknisi.", None)
        return (get_bad_rx_summary(), get_main_menu_keyboard())

    # 3. Modem Belum Setting / ONT Baru
    if cmd in ["ontbaru", "unconf", "newont"]:
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin / Teknisi.", None)
        return (get_unconfigured_onts(), get_main_menu_keyboard())

    # 4. Cek Server Stats
    if cmd in ["server", "status"]:
        if is_admin:
            return (get_server_stats(), get_main_menu_keyboard())

    # 5. Cek Modem / ONT Status
    if cmd in ["cek", "info"]:
        target = rest
        if not target and registered_tag:
            target = registered_tag

        if not is_admin:
            dev_target = customer_dev or (find_device(target) if target else None)
            if not dev_target:
                return ("⚠️ Nomor WhatsApp Anda belum terhubung ke modem. Ketik `daftar <id_pppoe>` terlebih dahulu.", None)
            return (get_customer_friendly_summary(dev_target), None)

        if not target:
            return ("⚠️ Silakan sertakan Username PPPoE atau Serial Number.\n_Contoh:_ `cek cucimotor`", None)

        dev = find_device(target)
        if not dev:
            return (f"❌ Modem `{target}` tidak ditemukan di database GenieACS.", None)

        pppoe_user, summary_text, wifi_on = get_device_summary(dev)
        dev_id = dev.get("_id")
        kb = get_device_inline_keyboard(pppoe_user, dev_id, wifi_on)
        return (summary_text, kb)

    # 6. Klien WiFi Terhubung
    if cmd in ["klien", "client", "clients"]:
        target = rest or registered_tag
        if not target:
            return ("⚠️ Gunakan: `klien <username_pppoe/sn>`", None)
        dev = find_device(target)
        if not dev:
            return (f"❌ Modem `{target}` tidak ditemukan.", None)
        return (get_device_clients(dev), None)

    # 7. Reboot ONT
    if cmd in ["reboot", "restart"]:
        target = rest or registered_tag
        if not target and not is_admin and customer_dev:
            target = customer_dev.get("_id")
        if not target:
            if not is_admin:
                return ("⚠️ Nomor WhatsApp Anda belum terhubung ke modem mana pun.", None)
            return ("⚠️ Gunakan: `reboot <username_pppoe/sn>`", None)
        dev = find_device(target)
        if not dev:
            return (f"❌ Modem `{target}` tidak ditemukan.", None)
        ok, msg = reboot_device_task(dev)
        if not is_admin and ok:
            p_name = get_device_pppoe_username(dev)
            return (
                f"🔄 *Perintah Restart Terkirim!*\n"
                f"Modem Anda (*{p_name}*) sedang memulai ulang (reboot).\n"
                f"Mohon tunggu sekitar 1-2 menit hingga lampu PON/Internet menyala stabil kembali.",
                None
            )
        return (f"{'✅' if ok else '❌'} {msg}", None)

    # 8. WiFi ON / OFF
    if cmd == "wifioff":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        target = rest
        if not target:
            return ("⚠️ Gunakan: `wifioff <username/sn>`", None)
        dev = find_device(target)
        if not dev:
            return (f"❌ Modem `{target}` tidak ditemukan.", None)
        ok, msg = set_wifi_power(dev, enable=False)
        return (f"{'✅' if ok else '❌'} {msg}", None)

    if cmd == "wifion":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        target = rest
        if not target:
            return ("⚠️ Gunakan: `wifion <username/sn>`", None)
        dev = find_device(target)
        if not dev:
            return (f"❌ Modem `{target}` tidak ditemukan.", None)
        ok, msg = set_wifi_power(dev, enable=True)
        return (f"{'✅' if ok else '❌'} {msg}", None)

    # 9. Ubah WiFi (SSID & Password)
    if cmd == "wifi":
        sub_parts = rest.split()
        if is_admin and len(sub_parts) >= 3:
            target, new_ssid, new_pass = sub_parts[0], sub_parts[1], sub_parts[2]
            dev = find_device(target)
            if not dev:
                return (f"❌ Modem `{target}` tidak ditemukan.", None)
            ok, msg = set_wifi_credentials(dev, new_ssid=new_ssid, new_password=new_pass)
            if ok:
                return (f"✅ *Berhasil Mengubah Pengaturan WiFi!*\n• Pelanggan: `{target}`\n• SSID: `{new_ssid}`\n• Sandi: `{new_pass}`\nStatus: Terkirim via TR-069.", None)
            return (f"❌ Gagal: {msg}", None)
        elif not is_admin:
            dev_target = customer_dev or (find_device(registered_tag) if registered_tag else None)
            if not dev_target:
                return ("⚠️ Nomor Anda belum terhubung ke modem mana pun. Ketik `daftar <id_pppoe>` terlebih dahulu.", None)
            if len(sub_parts) < 2:
                return ("⚠️ Format salah. Gunakan:\n`wifi <nama_wifi_baru> <sandi_baru>`\n_Contoh:_ `wifi MyHome SandiRahasia123`", None)
            new_ssid, new_pass = sub_parts[0], sub_parts[1]
            if len(new_pass) < 8:
                return ("⚠️ Kata sandi WiFi minimal harus 8 karakter demi keamanan WPA2-PSK.\n_Contoh:_ `wifi MyHome SandiRahasia123`", None)
            ok, msg = set_wifi_credentials(dev_target, new_ssid=new_ssid, new_password=new_pass)
            if ok:
                return (
                    f"✅ *WiFi Anda Berhasil Diperbarui!*\n"
                    f"• Nama WiFi Baru : *{new_ssid}*\n"
                    f"• Sandi Baru : *{new_pass}*\n\n"
                    f"Pengaturan telah dikirim ke modem. Silakan sambungkan kembali perangkat HP/Laptop Anda dengan kata sandi baru.",
                    None
                )
            return (f"❌ Gagal memperbarui WiFi: {msg}", None)
        else:
            if is_admin:
                return ("⚠️ Format salah. Gunakan:\n`wifi <user> <nama_wifi_baru> <sandi_baru>`\n_Contoh:_ `wifi cucimotor Alijaya-Net 12345678`", None)
            else:
                return ("⚠️ Format salah. Gunakan:\n`wifi <nama_wifi_baru> <sandi_baru>`\n_Contoh:_ `wifi WiFi-Saya SandiRahasia123`", None)

    # 10. Ubah SSID saja
    if cmd == "ssid":
        if is_admin:
            sub_parts = rest.split(maxsplit=1)
            if len(sub_parts) >= 2:
                target, new_ssid = sub_parts[0], sub_parts[1]
                dev = find_device(target)
                if not dev:
                    return (f"❌ Modem `{target}` tidak ditemukan.", None)
                ok, msg = set_wifi_credentials(dev, new_ssid=new_ssid)
                if ok:
                    return (f"✅ *Berhasil Mengubah SSID!*\n• Pelanggan: `{target}`\n• SSID Baru: `{new_ssid}`", None)
                return (f"❌ Gagal: {msg}", None)
            return ("⚠️ Gunakan: `ssid <username_pppoe> <nama_baru>`", None)
        else:
            dev_target = customer_dev or (find_device(registered_tag) if registered_tag else None)
            if not dev_target:
                return ("⚠️ Nomor Anda belum terhubung ke modem mana pun. Ketik `daftar <id_pppoe>` terlebih dahulu.", None)
            if not rest:
                return ("⚠️ Format salah. Gunakan:\n`ssid <nama_wifi_baru>`\n_Contoh:_ `ssid MyHome-WiFi`", None)
            new_ssid = rest.strip()
            ok, msg = set_wifi_credentials(dev_target, new_ssid=new_ssid)
            if ok:
                return (
                    f"✅ *Nama WiFi Berhasil Diubah!*\n"
                    f"• Nama WiFi Baru : *{new_ssid}*\n\n"
                    f"Pengaturan telah dikirim ke modem. Silakan sambungkan kembali perangkat HP Anda.",
                    None
                )
            return (f"❌ Gagal mengubah nama WiFi: {msg}", None)

    # 11. Ubah Password saja
    if cmd in ["pass", "password", "sandi"]:
        if is_admin:
            sub_parts = rest.split(maxsplit=1)
            if len(sub_parts) >= 2:
                target, new_pass = sub_parts[0], sub_parts[1]
                if len(new_pass) < 8:
                    return ("⚠️ Kata sandi minimal 8 karakter.", None)
                dev = find_device(target)
                if not dev:
                    return (f"❌ Modem `{target}` tidak ditemukan.", None)
                ok, msg = set_wifi_credentials(dev, new_password=new_pass)
                if ok:
                    return (f"✅ *Berhasil Mengubah Sandi WiFi!*\n• Pelanggan: `{target}`\n• Sandi Baru: `{new_pass}`", None)
                return (f"❌ Gagal: {msg}", None)
            return ("⚠️ Gunakan: `pass <username_pppoe> <sandi_baru>`", None)
        else:
            dev_target = customer_dev or (find_device(registered_tag) if registered_tag else None)
            if not dev_target:
                return ("⚠️ Nomor Anda belum terhubung ke modem mana pun. Ketik `daftar <id_pppoe>` terlebih dahulu.", None)
            if not rest:
                return ("⚠️ Format salah. Gunakan:\n`pass <sandi_baru>`\n_Contoh:_ `pass SandiRahasia123`", None)
            new_pass = rest.split()[0].strip()
            if len(new_pass) < 8:
                return ("⚠️ Kata sandi minimal harus 8 karakter demi keamanan WPA2-PSK.\n_Contoh:_ `pass SandiRahasia123`", None)
            ok, msg = set_wifi_credentials(dev_target, new_password=new_pass)
            if ok:
                return (
                    f"✅ *Kata Sandi WiFi Berhasil Diubah!*\n"
                    f"• Kata Sandi Baru : *{new_pass}*\n\n"
                    f"Pengaturan telah dikirim ke modem. Silakan sambungkan kembali perangkat HP/Laptop Anda dengan kata sandi baru.",
                    None
                )
            return (f"❌ Gagal mengubah kata sandi: {msg}", None)

    # 12. Add/Set WAN PPPoE
    if cmd == "addwan":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        sub_parts = rest.split()
        if len(sub_parts) >= 3:
            target = sub_parts[0]
            pppoe_user = sub_parts[1]
            pppoe_pass = sub_parts[2]
            vlan_id = sub_parts[3] if len(sub_parts) > 3 else None
            dev = find_device(target)
            if not dev:
                return (f"❌ Modem `{target}` tidak ditemukan.", None)
            ok, msg = add_or_set_wan_pppoe(dev, pppoe_user, pppoe_pass, vlan_id)
            return (f"{'✅' if ok else '❌'} {msg}", None)
        return ("⚠️ Format salah. Gunakan:\n`addwan <sn/user> <user_pppoe> <pass_pppoe> [vlan_id]`", None)

    # 13. Superadmin Password
    if cmd == "superadmin":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        sub_parts = rest.split(maxsplit=1)
        if len(sub_parts) >= 2:
            target, new_pass = sub_parts[0], sub_parts[1]
            dev = find_device(target)
            if not dev:
                return (f"❌ Modem `{target}` tidak ditemukan.", None)
            ok, msg = set_superadmin_password(dev, new_pass)
            return (f"{'✅' if ok else '❌'} {msg}", None)
        return ("⚠️ Gunakan: `superadmin <username/sn> <password_baru>`", None)

    # 14. Factory Reset
    if cmd == "factoryreset":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        target = rest
        if not target:
            return ("⚠️ Gunakan: `factoryreset <username/sn>`", None)
        dev = find_device(target)
        if not dev:
            return (f"❌ Modem `{target}` tidak ditemukan.", None)
        ok, msg = factory_reset_device(dev)
        return (f"{'✅' if ok else '❌'} {msg}", None)

    # 15. Ping Diagnostics
    if cmd == "ping":
        sub_parts = rest.split()
        if sub_parts:
            target = sub_parts[0]
            host = sub_parts[1] if len(sub_parts) > 1 else "8.8.8.8"
            dev = find_device(target)
            if not dev:
                return (f"❌ Modem `{target}` tidak ditemukan.", None)
            ok, msg = ping_diagnostics_task(dev, host)
            return (f"{'✅' if ok else '❌'} {msg}", None)
        return ("⚠️ Gunakan: `ping <username/sn> [host]`", None)

    # 15.5. Tagging Nomor WhatsApp Pelanggan (Admin)
    if cmd == "tag":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        sub_parts = rest.split()
        if len(sub_parts) < 2:
            return ("⚠️ Format salah. Gunakan:\n`tag <username_pppoe/sn> <nomor_wa>`\n_Contoh:_ `tag cucimotor 081234567890`", None)
        target_user, raw_phone = sub_parts[0], sub_parts[1]
        dev = find_device(target_user)
        if not dev:
            return (f"❌ Modem `{target_user}` tidak ditemukan.", None)
        clean_phone = normalize_phone(raw_phone)
        if len(clean_phone) < 8:
            return (f"⚠️ Nomor WhatsApp `{raw_phone}` tidak valid.", None)
        add_device_tag(dev["_id"], clean_phone)
        pppoe_name = get_device_pppoe_username(dev)
        return (
            f"✅ *Tag WhatsApp Berhasil Ditambahkan!*\n"
            f"• Pelanggan : `{pppoe_name}`\n"
            f"• Device ID : `{dev.get('_id')}`\n"
            f"• Nomor Tag : `{clean_phone}`\n\n"
            f"Pelanggan kini dapat langsung chat bot untuk cek status & ubah WiFi secara mandiri!",
            None
        )

    if cmd == "untag":
        if not is_admin:
            return ("⛔ Perintah ini khusus untuk Admin.", None)
        sub_parts = rest.split()
        if len(sub_parts) < 2:
            return ("⚠️ Format salah. Gunakan:\n`untag <username_pppoe/sn> <nomor_wa>`\n_Contoh:_ `untag cucimotor 081234567890`", None)
        target_user, raw_phone = sub_parts[0], sub_parts[1]
        dev = find_device(target_user)
        if not dev:
            return (f"❌ Modem `{target_user}` tidak ditemukan.", None)
        clean_phone = normalize_phone(raw_phone)
        remove_device_tag(dev["_id"], clean_phone)
        return (f"🗑️ Tag `{clean_phone}` berhasil dihapus dari modem `{target_user}`.", None)

    # 15.6. Pendaftaran Mandiri Pelanggan (Customer Self-Registration)
    if cmd == "daftar":
        if not rest:
            return ("⚠️ Format salah. Gunakan:\n`daftar <id_pppoe>`\n_Contoh:_ `daftar cucimotor`", None)
        target_user = rest.split()[0]
        dev = find_device(target_user)
        if not dev:
            return (f"❌ Pelanggan `{target_user}` tidak ditemukan di sistem GenieACS. Pastikan ID PPPoE Anda benar.", None)
        clean_phone = normalize_phone(sender_id)
        if clean_phone and len(clean_phone) >= 8:
            add_device_tag(dev["_id"], clean_phone)
        pppoe_name = get_device_pppoe_username(dev)
        return (
            f"✅ *Pendaftaran Layanan Mandiri Berhasil!*\n"
            f"Nomor WhatsApp Anda (*{clean_phone or sender_id}*) kini telah terhubung ke modem: *{pppoe_name}*.\n\n"
            f"Silakan gunakan perintah mandiri berikut kapan saja:\n"
            f"• `cek` ➔ Cek nama WiFi, kata sandi & status sinyal\n"
            f"• `wifi <nama_baru> <sandi_baru>` ➔ Ganti nama & sandi WiFi\n"
            f"• `pass <sandi_baru>` ➔ Ganti sandi WiFi saja (min. 8 karakter)\n"
            f"• `ssid <nama_baru>` ➔ Ganti nama WiFi saja\n"
            f"• `reboot` ➔ Restart modem jika koneksi lambat",
            None
        )

    # 16. Fallback Gemini AI / Percakapan Cerdas
    if gemini_key and is_valid_token(gemini_key):
        ai_reply = ask_gemini_ai(gemini_key, gemini_model, raw, sender_id)
        if ai_reply:
            return (ai_reply, None)

    # Default if not understood
    if is_admin:
        return (f"⚠️ Perintah `{raw}` tidak dikenali. Ketik `menu` untuk melihat daftar perintah.", get_main_menu_keyboard())
    else:
        return (f"👋 Halo! Nomor Anda belum terdaftar. Ketik `daftar <id_pelanggan>` untuk menghubungkan akun internet Anda.", None)


def handle_incoming_message(token, chat_id, user_text, gemini_key, model_name):
    txt = user_text.strip()
    state = USER_STATES.get(chat_id)

    # Cancel command
    if txt.lower() in ["/batal", "/cancel", "batal", "cancel"]:
        USER_STATES.pop(chat_id, None)
        send_telegram(token, chat_id, "✅ Operasi dibatalkan.", reply_markup=get_main_menu_keyboard())
        return

    # Menu Buttons Handlers khusus Telegram
    if txt in ["🔍 Cek Modem"]:
        USER_STATES[chat_id] = {"action": "wait_cek"}
        send_telegram(token, chat_id, "🔍 *Cek Modem*: Silakan ketik Username PPPoE atau Serial Number (contoh: `cucimotor`):", reply_markup=get_main_menu_keyboard())
        return

    if txt in ["⚠️ Cek Redaman Kritis", "/redaman", "/los"]:
        USER_STATES.pop(chat_id, None)
        send_telegram(token, chat_id, get_bad_rx_summary(), reply_markup=get_main_menu_keyboard())
        return

    if txt in ["🆕 Modem Belum Setting", "/ontbaru", "/unconf"]:
        USER_STATES.pop(chat_id, None)
        send_telegram(token, chat_id, get_unconfigured_onts(), reply_markup=get_main_menu_keyboard())
        return

    if txt in ["📊 Status Server STB", "📊 Status Server", "/server", "/status", "status", "server"]:
        USER_STATES.pop(chat_id, None)
        send_telegram(token, chat_id, get_server_stats(), reply_markup=get_main_menu_keyboard())
        return

    if txt in ["❓ Bantuan / Help", "/help", "/menu", "/start", "menu", "help", "bantuan"]:
        USER_STATES.pop(chat_id, None)
        reply_text, markup = process_agent_command("menu", sender_id=chat_id, is_admin=True)
        send_telegram(token, chat_id, reply_text, reply_markup=markup or get_main_menu_keyboard())
        return

    if txt in ["👥 Daftar Klien WiFi", "👥 Cek Klien", "/klien"]:
        USER_STATES[chat_id] = {"action": "wait_klien"}
        send_telegram(token, chat_id, "👥 *Daftar Klien Terhubung*: Silakan ketik Username PPPoE atau Serial Number (contoh: `cucimotor`):", reply_markup=get_main_menu_keyboard())
        return

    if txt in ["🔄 Reboot Modem", "/reboot"]:
        USER_STATES[chat_id] = {"action": "wait_reboot"}
        send_telegram(token, chat_id, "🔄 *Reboot Modem*: Silakan ketik Username PPPoE atau Serial Number modem yang ingin di-restart (contoh: `cucimotor`):", reply_markup=get_main_menu_keyboard())
        return

    if txt in ["🌐 Tambah / Set WAN", "/addwan"]:
        USER_STATES[chat_id] = {"action": "wait_wan_add"}
        wan_guide = (
            "🌐 *Tambah / Konfigurasi WAN PPPoE*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Silakan ketik data dengan format:\n"
            "`<sn_modem> <user_pppoe> <password_pppoe> [vlan_id]`\n\n"
            "📌 *Contoh Tanpa VLAN:*\n"
            "`ZTEGC1234567 cucimotor 12345678`\n\n"
            "📌 *Contoh Dengan VLAN:*\n"
            "`ZTEGC1234567 cucimotor 12345678 100`\n\n"
            "_(Ketik langsung format di atas untuk mengeksekusi)_"
        )
        send_telegram(token, chat_id, wan_guide, reply_markup=get_main_menu_keyboard())
        return

    if txt in ["📶 Ubah WiFi / Sandi", "/wifi"]:
        USER_STATES.pop(chat_id, None)
        wifi_guide = (
            "📶 *Ubah Pengaturan WiFi Pelanggan*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Silakan gunakan salah satu format perintah berikut:\n\n"
            "1️⃣ *Ubah Nama & Sandi WiFi Sekaligus:*\n"
            "`wifi <user_pppoe> <nama_wifi_baru> <sandi_baru>`\n"
            "_Contoh:_ `wifi cucimotor Alijaya-Net 12345678`\n\n"
            "2️⃣ *Ubah Nama WiFi (SSID) Saja:*\n"
            "`ssid <user_pppoe> <nama_wifi_baru>`\n"
            "_Contoh:_ `ssid cucimotor Alijaya-Net`\n\n"
            "3️⃣ *Ubah Sandi WiFi Saja (min. 8 Karakter):*\n"
            "`pass <user_pppoe> <sandi_baru>`\n"
            "_Contoh:_ `pass cucimotor 12345678`\n\n"
            "_(Atau ketik `/cek <user>` untuk mengubah tombol interaktif per perangkat)_"
        )
        send_telegram(token, chat_id, wifi_guide, reply_markup=get_main_menu_keyboard())
        return

    # Check conversation states jika ada aksi interaktif sebelumnya
    if state and state.get("action") == "wait_cek":
        USER_STATES.pop(chat_id, None)
        dev = find_device(txt)
        if not dev:
            send_telegram(token, chat_id, f"❌ Modem `{txt}` tidak ditemukan di database GenieACS.", reply_markup=get_main_menu_keyboard())
            return
        pppoe_user, summary_text, wifi_on = get_device_summary(dev)
        dev_id = dev.get("_id")
        send_telegram(token, chat_id, summary_text, reply_markup=get_device_inline_keyboard(pppoe_user, dev_id, wifi_on))
        return

    if state and state.get("action") == "wait_klien":
        USER_STATES.pop(chat_id, None)
        dev = find_device(txt)
        if not dev:
            send_telegram(token, chat_id, f"❌ Modem `{txt}` tidak ditemukan.", reply_markup=get_main_menu_keyboard())
            return
        send_telegram(token, chat_id, get_device_clients(dev), reply_markup=get_main_menu_keyboard())
        return

    if state and state.get("action") == "wait_reboot":
        USER_STATES.pop(chat_id, None)
        dev = find_device(txt)
        if not dev:
            send_telegram(token, chat_id, f"❌ Modem `{txt}` tidak ditemukan.", reply_markup=get_main_menu_keyboard())
            return
        ok, msg = reboot_device_task(dev)
        send_telegram(token, chat_id, f"{'✅' if ok else '❌'} {msg}", reply_markup=get_main_menu_keyboard())
        return

    if state and state.get("action") == "wait_wan_add":
        USER_STATES.pop(chat_id, None)
        parts = txt.split()
        if len(parts) >= 3:
            target = parts[0]
            pppoe_user = parts[1]
            pppoe_pass = parts[2]
            vlan_id = parts[3] if len(parts) > 3 else None
            dev = find_device(target)
            if not dev:
                send_telegram(token, chat_id, f"❌ Modem `{target}` tidak ditemukan.", reply_markup=get_main_menu_keyboard())
                return
            ok, msg = add_or_set_wan_pppoe(dev, pppoe_user, pppoe_pass, vlan_id)
            send_telegram(token, chat_id, f"{'✅' if ok else '❌'} {msg}", reply_markup=get_main_menu_keyboard())
            return
        else:
            send_telegram(token, chat_id, "⚠️ Format salah. Harap ketik: `<sn_modem> <user_pppoe> <password_pppoe> [vlan_id]`", reply_markup=get_main_menu_keyboard())
            return

    if state and state.get("action") == "wait_ssid":
        target = state.get("target")
        USER_STATES.pop(chat_id, None)
        dev = find_device(target)
        if not dev:
            send_telegram(token, chat_id, f"❌ Modem `{target}` tidak ditemukan.", reply_markup=get_main_menu_keyboard())
            return
        ok, msg = set_wifi_credentials(dev, new_ssid=txt)
        if ok:
            send_telegram(token, chat_id, f"✅ *Berhasil Mengubah SSID!*\n• Pelanggan: `{target}`\n• SSID Baru: `{txt}`", reply_markup=get_main_menu_keyboard())
        else:
            send_telegram(token, chat_id, f"❌ Gagal: {msg}", reply_markup=get_main_menu_keyboard())
        return

    if state and state.get("action") == "wait_pass":
        target = state.get("target")
        USER_STATES.pop(chat_id, None)
        if len(txt) < 8:
            send_telegram(token, chat_id, "⚠️ Sandi WiFi minimal harus 8 karakter.", reply_markup=get_main_menu_keyboard())
            return
        dev = find_device(target)
        if not dev:
            send_telegram(token, chat_id, f"❌ Modem `{target}` tidak ditemukan.", reply_markup=get_main_menu_keyboard())
            return
        ok, msg = set_wifi_credentials(dev, new_password=txt)
        if ok:
            send_telegram(token, chat_id, f"✅ *Berhasil Mengubah Sandi WiFi!*\n• Pelanggan: `{target}`\n• Sandi Baru: `{txt}`", reply_markup=get_main_menu_keyboard())
        else:
            send_telegram(token, chat_id, f"❌ Gagal: {msg}", reply_markup=get_main_menu_keyboard())
        return

    if state and state.get("action") == "wait_wan":
        target = state.get("target")
        USER_STATES.pop(chat_id, None)
        parts = txt.split()
        if len(parts) >= 2:
            p_user = parts[0]
            p_pass = parts[1]
            p_vlan = parts[2] if len(parts) > 2 else None
            dev = find_device(target)
            if not dev:
                send_telegram(token, chat_id, f"❌ Modem `{target}` tidak ditemukan.", reply_markup=get_main_menu_keyboard())
                return
            ok, msg = add_or_set_wan_pppoe(dev, p_user, p_pass, p_vlan)
            send_telegram(token, chat_id, f"{'✅' if ok else '❌'} {msg}", reply_markup=get_main_menu_keyboard())
            return
        else:
            send_telegram(token, chat_id, "⚠️ Format salah. Harap ketik: `<user_pppoe> <password_pppoe> [vlan_id]`", reply_markup=get_main_menu_keyboard())
            return

    # Jalankan perintah melalui unified command processor
    reply_text, markup = process_agent_command(
        user_text=txt,
        sender_id=chat_id,
        is_admin=True,
        gemini_key=gemini_key,
        gemini_model=model_name
    )
    if reply_text:
        send_telegram(token, chat_id, reply_text, reply_markup=markup or get_main_menu_keyboard())


def check_proactive_alerts(token, admin_ids):
    try:
        db = get_db()
        if db is None:
            return
            
        cursor = db.devices.find({"VirtualParameters.RXPower": {"$exists": True}})
        for d in cursor:
            vp = d.get("VirtualParameters", {})
            rx_dict = vp.get("RXPower", {})
            rx_val = rx_dict.get("_value") if isinstance(rx_dict, dict) else None
            
            if rx_val is None:
                continue
                
            try:
                rx_float = float(rx_val)
                dev_id = d.get("_id", "Unknown")
                pppoe = vp.get("pppoeUsername", {}).get("_value") if isinstance(vp.get("pppoeUsername"), dict) else dev_id
                
                if rx_float < -27.0 or rx_float > -8.0:
                    alert_key = f"{dev_id}_bad_rx"
                    last_alert = ALERT_HISTORY.get(alert_key, 0)
                    now = time.time()
                    
                    if (now - last_alert) > 3600:
                        ALERT_HISTORY[alert_key] = now
                        drop_msg = (
                            f"🚨 *[ALERT REDAMAN DROP KRITIS]*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"• *Pelanggan*: `{pppoe.upper()}`\n"
                            f"• *Redaman Saat Ini*: `{rx_val} dBm` 🔴\n"
                            f"• *Penyebab*: Kemungkinan kabel optik terjepit, kotor, atau patchcord bermasalah.\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"👉 _Segera lakukan pengecekan fisik di lapangan._"
                        )
                        for aid in admin_ids:
                            send_telegram(token, aid, drop_msg)

                        # Kirim notifikasi ke WhatsApp Admin jika aktif
                        try:
                            cfgs = get_config()
                            wa_enabled = cfgs.get("agent.whatsapp.enabled", "true").lower() == "true"
                            wa_admins = cfgs.get("agent.whatsapp.admin_numbers", BRAND_PHONE)
                            if wa_enabled and wa_admins:
                                wa_list = [w.strip() for w in wa_admins.replace(";", ",").split(",") if w.strip()]
                                for wa_no in wa_list:
                                    requests.post("http://127.0.0.1:7559/send", json={"to": wa_no, "text": drop_msg}, timeout=2.0)
                        except Exception:
                            pass
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"Error in watchdog: {e}")


HTML_CONFIG_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pengaturan Bot AI & WhatsApp - ALIJAYA NET</title>
  <style>
    :root {
      --bg: #050833;
      --card: #080d22;
      --card-inner: #040714;
      --border: #1c274c;
      --primary: #00e5ff;
      --primary-btn: #046380;
      --primary-hover: #00b4d8;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif; }
    html { min-height: 100vh; background-color: var(--bg); }
    body { background-color: transparent; color: var(--text); padding: 14px; display: flex; justify-content: center; }
    .container { width: 100%; max-width: 860px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 22px; box-shadow: 0 4px 25px rgba(0,0,0,0.45); }
    
    .header { text-align: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 14px; position: relative; }
    .header h2 { font-size: 1.35rem; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; font-weight: 700; letter-spacing: 0.3px; }
    .header p { color: var(--text-muted); font-size: 0.84rem; margin-top: 4px; }
    .btn-header-logout {
      position: absolute; right: 0; top: 0;
      background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fca5a5; padding: 5px 12px; border-radius: 6px; cursor: pointer;
      font-size: 0.78rem; font-weight: 600; transition: all 0.2s;
    }
    .btn-header-logout:hover { background: #ef4444; color: #fff; }

    /* Tabs Navigation */
    .tabs { display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
    .tab-btn { flex: 1; padding: 10px 14px; background: var(--card-inner); border: 1px solid var(--border); border-radius: 6px; color: var(--text-muted); font-weight: 600; font-size: 0.88rem; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px; }
    .tab-btn:hover { background: #0f1c3f; color: #fff; }
    .tab-btn.active { background: var(--primary-btn); color: #fff; border-color: var(--primary); font-weight: 700; box-shadow: 0 0 10px rgba(0,229,255,0.25); }
    
    .tab-pane { display: none; }
    .tab-pane.active { display: block; animation: fadeIn 0.2s ease-in-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    .form-group { margin-bottom: 16px; }
    label { display: block; font-size: 0.86rem; font-weight: 600; margin-bottom: 6px; color: var(--text); }
    .hint { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; line-height: 1.4; }
    input[type="text"], input[type="password"], select, textarea {
      width: 100%; padding: 10px 14px; background: var(--card-inner); border: 1px solid var(--border); border-radius: 6px; color: #fff; font-size: 0.92rem; outline: none; transition: border-color 0.2s, box-shadow 0.2s;
    }
    input:focus, select:focus, textarea:focus { border-color: var(--primary); box-shadow: 0 0 8px rgba(0, 229, 255, 0.35); }
    textarea { resize: vertical; min-height: 60px; }

    /* WhatsApp Status Card */
    .status-card { background: var(--card-inner); border: 1px solid var(--border); border-radius: 8px; padding: 18px; margin-bottom: 18px; text-align: center; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; }
    .badge-open { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid var(--success); }
    .badge-qr { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid var(--warning); }
    .badge-connecting { background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid var(--primary); }
    .badge-disconnected { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid var(--danger); }

    .qr-box { margin-top: 12px; }
    .qr-box img { width: 230px; height: 230px; background: #fff; padding: 8px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.6); }

    .btn-row { display: flex; gap: 12px; margin-top: 22px; }
    button { flex: 1; padding: 11px 16px; border: none; border-radius: 6px; font-weight: 600; font-size: 0.92rem; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; }
    .btn-save { background: linear-gradient(135deg, #046380 0%, #0891b2 100%); color: #fff; font-weight: 700; border: 1px solid #00e5ff; box-shadow: 0 2px 8px rgba(4,99,128,0.4); }
    .btn-save:hover { background: #00e5ff; color: #000; box-shadow: 0 0 14px rgba(0,229,255,0.6); }
    .btn-test { background: #131e3d; border: 1px solid #23355e; color: #e2e8f0; }
    .btn-test:hover { background: #1c2b54; color: #fff; }
    .btn-logout { background: #450a0a; color: #fca5a5; border: 1px solid #ef4444; padding: 6px 14px; font-size: 0.85rem; border-radius: 6px; margin-top: 10px; display: inline-flex; }
    .btn-logout:hover { background: #7f1d1d; color: #fff; }
    .btn-reset-wa {
      background: #450a0a;
      color: #fca5a5;
      border: 1px solid #dc2626;
      padding: 9px 18px;
      font-size: 0.88rem;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;
    }
    .btn-reset-wa:hover {
      background: #7f1d1d;
      color: #fff;
      box-shadow: 0 0 10px rgba(220,38,38,0.4);
    }

    .alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 0.9rem; display: none; }
    .alert-success { background: rgba(16, 185, 129, 0.15); border: 1px solid var(--success); color: #34d399; }
    .alert-error { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #f87171; }
    .back-link { display: inline-block; margin-top: 18px; text-decoration: none; color: var(--primary); font-size: 0.85rem; font-weight: 500; }
    .back-link:hover { text-decoration: underline; }

    .version-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px; }
    @media (max-width: 600px) {
      .version-grid { grid-template-columns: 1fr; }
    }

    /* In-Iframe styling: seamlessly blend with GenieACS SPA */
    body.in-iframe { padding: 8px 12px; }
    body.in-iframe .container { max-width: 100%; border: 1px solid var(--border); box-shadow: none; background: rgba(8, 13, 34, 0.85); }
    body.in-iframe #backToAcs { display: none !important; }
  </style></head>
<body>
  <div class="container">
    <div class="header">
      <div style="display: flex; align-items: center; justify-content: space-between; position: relative;">
        <h2 style="margin: 0 auto; display: flex; align-items: center; gap: 8px;">🤖 Pengaturan Bot AI & WhatsApp</h2>
        <button type="button" onclick="handleAdminLogout()" class="btn-header-logout">🚪 Logout</button>
      </div>
      <p>Panel Kontrol TR-069 GenieACS, Bot Telegram & Gateway WhatsApp Baileys</p>
    </div>

    <div id="alertBox" class="alert"></div>

    <div class="tabs">
      <button type="button" class="tab-btn active" onclick="switchTab('tab-wa')">📱 WhatsApp (Baileys)</button>
      <button type="button" class="tab-btn" onclick="switchTab('tab-tg')">✈️ Telegram Bot</button>
      <button type="button" class="tab-btn" onclick="switchTab('tab-brand')">🏢 Brand & AI</button>
      <button type="button" class="tab-btn" onclick="switchTab('tab-update')">🔄 Sistem & Update</button>
    </div>

    <form id="botForm">
      <!-- TAB 1: WHATSAPP (BAILEYS) -->
      <div id="tab-wa" class="tab-pane active">
        <div class="status-card">
          <span id="waBadge" class="badge badge-connecting">MEMUAT STATUS...</span>
          
          <div id="waConnectedBox" style="display: none;">
            <p style="color: #34d399; font-weight: 600; font-size: 1.05rem;">✅ Bot WhatsApp Siap Digunakan</p>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 4px;">Akun: <b id="waUser" style="color: #fff;">-</b></p>
            <button type="button" class="btn-logout" onclick="logoutWA()">🔴 Putus Koneksi / Logout</button>
          </div>

          <div id="waQrBox" class="qr-box" style="display: none;">
            <p style="font-size: 0.88rem; color: #fbbf24; font-weight: 600; margin-bottom: 6px;">📷 Pindai Kode QR WhatsApp</p>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 12px;">Buka WhatsApp di HP ➔ <b>Perangkat Tertaut</b> ➔ <b>Tautkan Perangkat</b></p>
            <img id="waQrImg" src="" alt="WhatsApp QR Code" />
            <p style="font-size: 0.75rem; color: var(--primary); margin-top: 8px;">Auto-refresh aktif setiap 3 detik 🔄</p>
          </div>

          <div id="waOfflineBox" style="display: none;">
            <p style="color: #f87171; font-size: 0.88rem;">⚠️ Service WhatsApp belum aktif di port 7559.<br>Pastikan daemon <code>genieacs-whatsapp.service</code> sedang berjalan.</p>
          </div>

          <div class="session-actions" style="margin-top: 18px; border-top: 1px solid var(--border); padding-top: 14px; text-align: center;">
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 8px;">
              Ingin mengganti nomor bot WhatsApp baru atau membuat ulang QR Code?
            </p>
            <button type="button" class="btn-reset-wa" onclick="resetWA()">
              🗑️ Hapus Sesi WhatsApp (Ganti Nomor Bot / Buat QR Baru)
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>Status Layanan Bot WhatsApp:</label>
          <select id="wa_enabled" name="wa_enabled">
            <option value="true">Aktif (Enabled) 🟢</option>
            <option value="false">Nonaktif (Disabled) 🔴</option>
          </select>
        </div>

        <div class="form-group">
          <label>Nomor WhatsApp Admin / Teknisi:</label>
          <textarea id="wa_admin_numbers" name="wa_admin_numbers" placeholder="Contoh: 081947215703, 081234567890"></textarea>
          <div class="hint">Nomor yang memiliki hak akses perintah administratif (cek, redaman, reboot, wifion/off, ssid, dll). Pisahkan koma jika lebih dari satu.</div>
        </div>
      </div>

      <!-- TAB 2: TELEGRAM BOT -->
      <div id="tab-tg" class="tab-pane">
        <div class="form-group">
          <label>Status Layanan Bot Telegram:</label>
          <select id="bot_enabled" name="enabled">
            <option value="true">Aktif (Enabled) 🟢</option>
            <option value="false">Nonaktif (Disabled) 🔴</option>
          </select>
        </div>

        <div class="form-group">
          <label>Token Bot Telegram:</label>
          <input type="text" id="bot_token" name="token" placeholder="Contoh: 123456789:AAFMD7X_xxxxxxxxxxxxxx">
          <div class="hint">Dapatkan dari @BotFather di Telegram.</div>
        </div>

        <div class="form-group">
          <label>Admin Chat ID / ID Grup Telegram:</label>
          <input type="text" id="admin_id" name="admin_id" placeholder="Contoh: 567858628 atau 567858628, -100987654321">
          <div class="hint">Dapatkan ID Anda dari @userinfobot. Bisa isi beberapa ID dipisah koma.</div>
        </div>

        <div style="margin-top: 14px;">
          <button type="button" id="btnTest" class="btn-test">🧪 Tes Kirim Pesan Telegram</button>
        </div>
      </div>

      <!-- TAB 3: BRANDING & AI -->
      <div id="tab-brand" class="tab-pane">
        <div class="form-group">
          <label>Nama Brand / ISP / RT-RW Net:</label>
          <input type="text" id="brand_name" name="brand_name" placeholder="ALIJAYA NET">
          <div class="hint">Nama usaha yang akan tampil pada header pesan Telegram & WhatsApp.</div>
        </div>

        <div class="form-group">
          <label>Nomor Telepon / WhatsApp Customer Service:</label>
          <input type="text" id="brand_phone" name="brand_phone" placeholder="081947215703">
          <div class="hint">Nomor kontak layanan bantuan pada footer pesan.</div>
        </div>

        <div class="form-group">
          <label>Google Gemini API Key (Opsional):</label>
          <input type="password" id="gemini_key" name="gemini_key" placeholder="AIzaSyDxxxxxxxxxxxxxxxxxxxx">
          <div class="hint">Untuk asisten AI percakapan cerdas. Kosongkan jika tidak memakai.</div>
        </div>
      </div>

      <!-- TAB 4: SISTEM & UPDATE -->
      <div id="tab-update" class="tab-pane">
        <div class="status-card" style="text-align: left; padding: 20px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
            <div>
              <span id="updateBadge" class="badge badge-open">MEMERIKSA VERSI...</span>
              <p style="color: var(--text-muted); font-size: 0.84rem; margin-top: 4px;">Repositori: <b style="color: #00e5ff;">github.com/alijayanet/genieacs-multitab-mod</b></p>
            </div>
            <button type="button" id="btnCheckUpdate" class="btn-test" style="flex: 0 0 auto; padding: 8px 16px; border-radius: 6px;" onclick="checkSystemUpdate()">🔍 Cek Pembaruan</button>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px;" class="version-grid">
            <div style="background: var(--card-inner); border: 1px solid var(--border); border-radius: 8px; padding: 14px;">
              <span style="font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Versi Server Ini (Lokal)</span>
              <div style="font-size: 1.15rem; font-weight: 700; color: #fff; margin-top: 4px; font-family: monospace;" id="localCommit">-</div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 6px;" id="localDate">-</div>
            </div>
            <div style="background: var(--card-inner); border: 1px solid var(--border); border-radius: 8px; padding: 14px;">
              <span style="font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Versi Terbaru (GitHub)</span>
              <div style="font-size: 1.15rem; font-weight: 700; color: #00e5ff; margin-top: 4px; font-family: monospace;" id="remoteCommit">-</div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 6px;" id="remoteDate">-</div>
            </div>
          </div>

          <div id="updateNoticeBox" style="background: rgba(4, 99, 128, 0.2); border: 1px solid #00e5ff; border-radius: 8px; padding: 14px; margin-bottom: 18px; display: none;">
            <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #00e5ff; font-size: 0.95rem;">
              ⚡ Pembaruan Baru Tersedia!
            </div>
            <p style="font-size: 0.85rem; color: #e2e8f0; margin-top: 6px;" id="updateNoticeMsg">-</p>
            <p style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;" id="updateNoticeBehind"></p>
          </div>

          <div style="margin-top: 10px;">
            <button type="button" id="btnApplyUpdate" class="btn-save" style="display: none; width: 100%; border-radius: 6px;" onclick="applySystemUpdate()">
              🚀 Perbarui Sistem Sekarang (1-Click Update)
            </button>
          </div>

          <!-- Terminal Log Box -->
          <div id="updateLogWrapper" style="display: none; margin-top: 18px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted);">📋 Log Proses Update:</span>
              <span id="updateProgressText" style="font-size: 0.78rem; color: var(--primary);">Menjalankan proses...</span>
            </div>
            <div id="updateLogBox" style="background: #02040a; border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-family: Consolas, 'Courier New', monospace; font-size: 0.8rem; color: #38bdf8; max-height: 200px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5;"></div>
          </div>
        </div>

        <div style="background: var(--card-inner); border: 1px solid var(--border); border-radius: 8px; padding: 14px; margin-top: 14px;">
          <h4 style="font-size: 0.88rem; color: #f8fafc; margin-bottom: 6px;">ℹ️ Informasi Pembaruan</h4>
          <p style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.5;">
            Fitur pembaruan ini akan secara otomatis menarik commit kode terbaru dari repositori GitHub, memperbarui modul backend & frontend GenieACS, dan me-restart service tanpa mengubah konfigurasi database MongoDB, token bot Telegram, maupun sesi WhatsApp yang sedang terhubung.
          </p>
        </div>
      </div>

      <div class="btn-row" id="saveBtnRow">
        <button type="submit" class="btn-save">💾 Simpan Semua Pengaturan</button>
      </div>
    </form>

    <div style="text-align: center;">
      <a href="/" class="back-link" id="backToAcs">⬅️ Kembali ke Dashboard GenieACS</a>
    </div>
  </div>

  <script>
    if (window.self !== window.top) {
      document.body.classList.add('in-iframe');
    }
    function botFetch(url, options) {
      const prefix = window.location.pathname.startsWith('/bot-proxy') ? '/bot-proxy' : '';
      const fullUrl = url.startsWith('/') ? prefix + url : prefix + '/' + url;
      return fetch(fullUrl, options);
    }
    window.botFetch = botFetch;
    document.getElementById('backToAcs').href = window.location.protocol + '//' + window.location.hostname + ':3000';

    function switchTab(tabId) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      
      const targetPane = document.getElementById(tabId);
      if (targetPane) targetPane.classList.add('active');

      if (typeof event !== 'undefined' && event && event.currentTarget && event.currentTarget.classList) {
        event.currentTarget.classList.add('active');
      } else {
        const clickedBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick') && b.getAttribute('onclick').indexOf(tabId) !== -1);
        if (clickedBtn) clickedBtn.classList.add('active');
      }

      const saveRow = document.getElementById('saveBtnRow');
      if (saveRow) {
        saveRow.style.display = (tabId === 'tab-update') ? 'none' : 'flex';
      }

      if (tabId === 'tab-update') {
        checkSystemUpdate(true);
      }
    }
    window.switchTab = switchTab;

    async function checkSystemUpdate(silenceSuccess) {
      const btn = document.getElementById('btnCheckUpdate');
      const badge = document.getElementById('updateBadge');
      if (btn) {
        btn.textContent = '⏳ Memeriksa...';
        btn.disabled = true;
      }
      try {
        const res = await botFetch('/api/system/update_status');
        const data = await res.json();
        if (!data.success) {
          showAlert('❌ ' + (data.error || 'Gagal memeriksa update'), false);
          return;
        }

        document.getElementById('localCommit').textContent = data.local_commit || '-';
        document.getElementById('localDate').textContent = 'Pembaruan: ' + (data.local_date || '-');
        document.getElementById('remoteCommit').textContent = data.remote_commit || '-';
        document.getElementById('remoteDate').textContent = 'Rilis: ' + (data.remote_date || '-');

        const btnApply = document.getElementById('btnApplyUpdate');
        const noticeBox = document.getElementById('updateNoticeBox');

        if (data.has_update) {
          badge.className = 'badge badge-qr';
          badge.textContent = '⚡ UPDATE TERSEDIA (' + (data.commits_behind || 1) + ' COMMIT)';
          noticeBox.style.display = 'block';
          document.getElementById('updateNoticeMsg').textContent = 'Pesan Rilis: ' + (data.remote_msg || '-');
          document.getElementById('updateNoticeBehind').textContent = 'Server ini tertinggal ' + (data.commits_behind || 1) + ' pembaruan dari GitHub.';
          btnApply.style.display = 'flex';
        } else {
          badge.className = 'badge badge-open';
          badge.textContent = '✅ SUDAH VERSI TERBARU';
          noticeBox.style.display = 'none';
          btnApply.style.display = 'none';
          if (!silenceSuccess) {
            showAlert('✅ Sistem Anda sudah menggunakan versi terbaru (' + data.local_commit + ').', true);
          }
        }
      } catch (err) {
        showAlert('❌ Gagal menghubungi server: ' + err.message, false);
      } finally {
        if (btn) {
          btn.textContent = '🔍 Cek Pembaruan';
          btn.disabled = false;
        }
      }
    }
    window.checkSystemUpdate = checkSystemUpdate;

    async function applySystemUpdate() {
      const confirmText = 'Apakah Anda yakin ingin memperbarui sistem ke versi terbaru dari GitHub?' + String.fromCharCode(10) + String.fromCharCode(10) + 'Service GenieACS akan direstart secara otomatis.';
      if (!confirm(confirmText)) {
        return;
      }

      const btnApply = document.getElementById('btnApplyUpdate');
      const logWrapper = document.getElementById('updateLogWrapper');
      const logBox = document.getElementById('updateLogBox');
      const progressText = document.getElementById('updateProgressText');

      btnApply.disabled = true;
      btnApply.textContent = '🚀 Sedang Memperbarui...';
      logWrapper.style.display = 'block';
      logBox.textContent = 'Memulai proses update...' + String.fromCharCode(10);
      progressText.textContent = 'Mengunduh dari GitHub...';

      try {
        const res = await botFetch('/api/system/update_apply', { method: 'POST' });
        const data = await res.json();
        if (data.logs) {
          logBox.textContent = data.logs;
        }
        if (data.success) {
          progressText.textContent = '✅ Berhasil!';
          progressText.style.color = '#34d399';
          showAlert('🎉 ' + data.message, true);
          
          let countdown = 6;
          const interval = setInterval(() => {
            countdown--;
            progressText.textContent = 'Memuat ulang halaman dalam ' + countdown + ' detik...';
            if (countdown <= 0) {
              clearInterval(interval);
              window.location.reload();
            }
          }, 1000);
        } else {
          progressText.textContent = '❌ Gagal';
          progressText.style.color = '#f87171';
          showAlert('❌ Gagal update: ' + (data.error || 'Terjadi kesalahan'), false);
          btnApply.disabled = false;
          btnApply.textContent = '🚀 Coba Perbarui Lagi';
        }
      } catch (err) {
        logBox.textContent += String.fromCharCode(10) + 'Error: ' + err.message;
        progressText.textContent = '⚠️ Service sedang restart...';
        let countdown = 6;
        const interval = setInterval(() => {
          countdown--;
          progressText.textContent = 'Service sedang restart. Memuat ulang dalam ' + countdown + ' detik...';
          if (countdown <= 0) {
            clearInterval(interval);
            window.location.reload();
          }
        }, 1000);
      }
    }
    window.applySystemUpdate = applySystemUpdate;

    function showAlert(msg, isSuccess) {
      const box = document.getElementById('alertBox');
      box.textContent = msg;
      box.className = 'alert ' + (isSuccess ? 'alert-success' : 'alert-error');
      box.style.display = 'block';
      box.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setTimeout(() => { box.style.display = 'none'; }, 6000);
    }

    // Load initial config
    botFetch('/api/config')
      .then(res => {
        if (!res.ok) throw new Error('Status: ' + res.status);
        return res.json();
      })
      .then(data => {
        document.getElementById('bot_enabled').value = data.enabled || 'true';
        document.getElementById('bot_token').value = data.token || '';
        document.getElementById('admin_id').value = data.admin_id || '';
        document.getElementById('brand_name').value = data.brand_name || '';
        document.getElementById('brand_phone').value = data.brand_phone || '';
        document.getElementById('gemini_key').value = data.gemini_key || '';
        document.getElementById('wa_enabled').value = data.wa_enabled !== undefined ? String(data.wa_enabled) : 'true';
        document.getElementById('wa_admin_numbers').value = data.wa_admin_numbers || '';
      })
      .catch(err => showAlert('❌ Gagal memuat konfigurasi: ' + err.message, false));

    // WhatsApp Live Status Polling
    let pollInterval = null;
    function updateWaStatus() {
      botFetch('/api/whatsapp/status')
        .then(res => res.json())
        .then(data => {
          const badge = document.getElementById('waBadge');
          const connBox = document.getElementById('waConnectedBox');
          const qrBox = document.getElementById('waQrBox');
          const offBox = document.getElementById('waOfflineBox');

          connBox.style.display = 'none';
          qrBox.style.display = 'none';
          offBox.style.display = 'none';

          if (data.connection === 'open') {
            badge.className = 'badge badge-open';
            badge.textContent = '🟢 TERHUBUNG (ONLINE)';
            connBox.style.display = 'block';
            document.getElementById('waUser').textContent = data.user ? (data.user.name || data.user.id) : '-';
          } else if (data.connection === 'qr') {
            badge.className = 'badge badge-qr';
            badge.textContent = '📷 MENUNGGU SCAN QR CODE';
            qrBox.style.display = 'block';
            if (data.qrImage) {
              document.getElementById('waQrImg').src = data.qrImage;
            } else if (data.qr) {
              document.getElementById('waQrImg').src = 'https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=' + encodeURIComponent(data.qr);
            }
          } else if (data.connection === 'connecting') {
            badge.className = 'badge badge-connecting';
            badge.textContent = '🔄 MENGHUBUNGKAN...';
          } else {
            badge.className = 'badge badge-disconnected';
            badge.textContent = '🔴 TERPUTUS (OFFLINE)';
            offBox.style.display = 'block';
          }
        })
        .catch(() => {
          const badge = document.getElementById('waBadge');
          badge.className = 'badge badge-disconnected';
          badge.textContent = '🔴 SERVICE OFFLINE';
          document.getElementById('waConnectedBox').style.display = 'none';
          document.getElementById('waQrBox').style.display = 'none';
          document.getElementById('waOfflineBox').style.display = 'block';
        });
    }

    updateWaStatus();
    pollInterval = setInterval(updateWaStatus, 3000);

    function logoutWA() {
      if (confirm('Yakin ingin memutuskan koneksi WhatsApp bot?')) {
        botFetch('/api/whatsapp/logout', { method: 'POST' })
          .then(res => res.json())
          .then(d => {
            showAlert('Sesi WhatsApp berhasil diputus', true);
            updateWaStatus();
          })
          .catch(err => showAlert('❌ Gagal logout WhatsApp: ' + err.message, false));
      }
    }
    window.logoutWA = logoutWA;

    function resetWA() {
      const confirmReset = '⚠️ PERHATIAN:' + String.fromCharCode(10) + String.fromCharCode(10) + 'Tindakan ini akan menghapus sesi WhatsApp bot di server dan membuat ulang QR Code.' + String.fromCharCode(10) + String.fromCharCode(10) + 'Apakah Anda yakin ingin melanjutkan?';
      if (confirm(confirmReset)) {
        const btn = document.querySelector('.btn-reset-wa');
        if (btn) {
          btn.disabled = true;
          btn.textContent = '⏳ Menghapus sesi WhatsApp...';
        }
        botFetch('/api/whatsapp/reset', { method: 'POST' })
          .then(res => res.json())
          .then(d => {
            showAlert('✅ ' + (d.message || 'Sesi WhatsApp berhasil dihapus. Silakan tunggu QR Code baru.'), true);
            setTimeout(updateWaStatus, 2000);
          })
          .catch(err => showAlert('❌ Gagal reset WhatsApp: ' + err.message, false))
          .finally(() => {
            if (btn) {
              btn.disabled = false;
              btn.textContent = '🗑️ Hapus Sesi WhatsApp (Ganti Nomor Bot / Buat QR Baru)';
            }
          });
      }
    }
    window.resetWA = resetWA;

    // Handle Form Submit
    document.getElementById('botForm').addEventListener('submit', function(e) {
      e.preventDefault();
      const payload = {
        enabled: document.getElementById('bot_enabled').value,
        token: document.getElementById('bot_token').value,
        admin_id: document.getElementById('admin_id').value,
        brand_name: document.getElementById('brand_name').value,
        brand_phone: document.getElementById('brand_phone').value,
        gemini_key: document.getElementById('gemini_key').value,
        wa_enabled: document.getElementById('wa_enabled').value,
        wa_admin_numbers: document.getElementById('wa_admin_numbers').value
      };

      botFetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          showAlert('✅ Konfigurasi Bot berhasil disimpan!', true);
        } else {
          showAlert('❌ ' + (data.message || 'Gagal menyimpan konfigurasi'), false);
        }
      })
      .catch(err => showAlert('❌ Error: ' + err.message, false));
    });

    // Test Telegram message
    document.getElementById('btnTest').addEventListener('click', function() {
      const token = document.getElementById('bot_token').value.trim();
      const adminId = document.getElementById('admin_id').value.trim();

      if (!token || !adminId) {
        showAlert('⚠️ Harap isi Token Bot dan Admin Chat ID terlebih dahulu!', false);
        return;
      }

      this.textContent = '⏳ Mengirim pesan...';
      this.disabled = true;

      const targetId = adminId.split(',')[0].trim();
      const testMsg = '🔔 *TES NOTIFIKASI GENIEACS BOT*' + String.fromCharCode(10) + String.fromCharCode(10) + 'Koneksi bot Telegram ALIJAYA NET berhasil terhubung dengan server!';
      const tgUrl = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + targetId + '&text=' + encodeURIComponent(testMsg) + '&parse_mode=Markdown';

      fetch(tgUrl)
      .then(res => res.json())
      .then(res => {
        if (res.ok) {
          showAlert('✅ Pesan tes Telegram berhasil terkirim ke ' + targetId + '!', true);
        } else {
          showAlert('❌ Gagal kirim Telegram: ' + (res.description || 'Unknown error'), false);
        }
      })
      .catch(err => showAlert('❌ Error: ' + err.message, false))
      .finally(() => {
        this.textContent = '🧪 Tes Kirim Pesan Telegram';
        this.disabled = false;
      });
    });

    async function handleAdminLogout() {
      if (confirm("Apakah Anda yakin ingin logout dari halaman pengaturan Bot?")) {
        try {
          await botFetch('/api/logout', { method: 'POST' });
        } catch (_) {}
        window.location.reload();
      }
    }
    window.handleAdminLogout = handleAdminLogout;
  </script>
</body>
</html>
"""


HTML_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login Administrator - Bot AI & WA GenieACS</title>
  <style>
    :root {
      --bg: #050833;
      --card: #080d22;
      --card-inner: #040714;
      --border: #1c274c;
      --primary: #00e5ff;
      --primary-btn: #046380;
      --primary-hover: #00b4d8;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body {
      background-color: var(--bg);
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }
    .login-box {
      width: 100%;
      max-width: 420px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 32px 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.6);
      text-align: center;
    }
    .logo-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: rgba(6, 182, 212, 0.15);
      color: var(--primary);
      font-size: 30px;
      margin-bottom: 16px;
      border: 1px solid rgba(6, 182, 212, 0.3);
    }
    h2 { font-size: 1.4rem; margin-bottom: 6px; color: #fff; font-weight: 700; }
    p.desc { font-size: 0.84rem; color: var(--text-muted); margin-bottom: 24px; line-height: 1.45; }
    .form-group { text-align: left; margin-bottom: 18px; }
    label { display: block; font-size: 0.84rem; font-weight: 600; margin-bottom: 6px; color: var(--text); }
    input {
      width: 100%;
      padding: 11px 14px;
      background: #040714;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: #fff;
      font-size: 0.94rem;
      outline: none;
      transition: border 0.2s;
    }
    input:focus { border-color: var(--primary); }
    .btn-login {
      width: 100%;
      padding: 12px;
      margin-top: 8px;
      background: var(--primary);
      color: #0b1120;
      font-weight: 700;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.96rem;
      transition: background 0.2s;
    }
    .btn-login:hover { background: var(--primary-hover); }
    .btn-login:disabled { opacity: 0.6; cursor: not-allowed; }
    .alert-error {
      display: none;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid var(--danger);
      color: #fca5a5;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 0.84rem;
      margin-bottom: 18px;
      text-align: left;
    }
    .footer { margin-top: 24px; font-size: 0.76rem; color: #64748b; }
  </style>
</head>
<body>
  <div class="login-box">
    <div class="logo-badge">🔐</div>
    <h2>Admin Login</h2>
    <p class="desc">Portal Pengaturan Bot AI & WhatsApp GenieACS.<br>Silakan masuk menggunakan akun Administrator GenieACS.</p>
    
    <div id="errMsg" class="alert-error"></div>
    
    <form id="loginForm" onsubmit="handleLogin(event)">
      <div class="form-group">
        <label for="username">Username Admin</label>
        <input type="text" id="username" autocomplete="username" placeholder="Masukkan username admin" required autofocus>
      </div>
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" autocomplete="current-password" placeholder="Masukkan password" required>
      </div>
      <button type="submit" id="btnSubmit" class="btn-login">Masuk ke Pengaturan</button>
    </form>
    
    <div class="footer">ALIJAYA NET TR-069 Management</div>
  </div>

  <script>
    function botFetch(url, options) {
      const prefix = window.location.pathname.startsWith('/bot-proxy') ? '/bot-proxy' : '';
      const fullUrl = url.startsWith('/') ? prefix + url : prefix + '/' + url;
      return fetch(fullUrl, options);
    }

    async function handleLogin(e) {
      e.preventDefault();
      const u = document.getElementById('username').value.trim();
      const p = document.getElementById('password').value;
      const btn = document.getElementById('btnSubmit');
      const err = document.getElementById('errMsg');
      
      err.style.display = 'none';
      btn.disabled = true;
      btn.textContent = 'Memverifikasi...';
      
      try {
        const res = await botFetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username: u, password: p})
        });
        const data = await res.json();
        if (data.success) {
          window.location.reload();
        } else {
          err.textContent = data.message || 'Username atau password salah / bukan akun admin.';
          err.style.display = 'block';
        }
      } catch (errEx) {
        err.textContent = 'Gagal terhubung ke server autentikasi: ' + errEx.message;
        err.style.display = 'block';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Masuk ke Pengaturan';
      }
    }
  </script>
</body>
</html>
"""

ACTIVE_ADMIN_SESSIONS = {}

def get_jwt_secret():
    secret = os.environ.get("GENIEACS_UI_JWT_SECRET") or os.environ.get("UI_JWT_SECRET")
    if not secret and os.path.exists("/opt/genieacs/genieacs.env"):
        try:
            with open("/opt/genieacs/genieacs.env", "r", encoding="utf-8") as f:
                for line in f:
                    if "GENIEACS_UI_JWT_SECRET=" in line:
                        secret = line.split("GENIEACS_UI_JWT_SECRET=")[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    return secret or ""

def verify_genieacs_jwt(token):
    secret = get_jwt_secret()
    if not secret:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h, p, s = parts
        msg = f"{h}.{p}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
        pad = "=" * ((4 - len(s) % 4) % 4)
        actual = base64.urlsafe_b64decode((s + pad).encode("ascii"))
        if not hmac.compare_digest(expected, actual):
            return None
        pad_p = "=" * ((4 - len(p) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode((p + pad_p).encode("ascii")).decode("utf-8"))
        return payload
    except Exception:
        return None

def verify_admin_login(username, password):
    db = get_db()
    if db is None:
        return False, "Database MongoDB tidak terhubung."
    user = db.users.find_one({"_id": username})
    if not user:
        return False, "Username atau password salah."
    roles = [r.strip() for r in user.get("roles", "").split(",") if r.strip()]
    if "admin" not in roles:
        return False, "Akun ini tidak memiliki hak akses Administrator GenieACS."
    salt = user.get("salt", "")
    expected_hash = user.get("password", "")
    computed_hash = hashlib.pbkdf2_hmac(
        "sha512",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        10000,
        dklen=128
    ).hex()
    if hmac.compare_digest(computed_hash, expected_hash):
        return True, "Login berhasil."
    return False, "Username atau password salah."



def get_system_update_status():
    repo_dirs = [
        "/root/genieacs-multitab-mod",
        "/opt/genieacs-multitab-mod",
        os.path.dirname(os.path.abspath(__file__))
    ]
    repo_dir = None
    for d in repo_dirs:
        if os.path.exists(os.path.join(d, ".git")):
            repo_dir = d
            break

    if not repo_dir:
        target_dir = "/root/genieacs-multitab-mod"
        try:
            subprocess.run(["git", "clone", "https://github.com/alijayanet/genieacs-multitab-mod.git", target_dir], timeout=35, check=True)
            repo_dir = target_dir
        except Exception as e:
            return {"success": False, "error": f"Gagal inisialisasi repositori Git: {e}"}

    try:
        local_hash = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], timeout=5).decode().strip()
        local_short = local_hash[:7]
        local_msg = subprocess.check_output(["git", "-C", repo_dir, "log", "-1", "--pretty=%s"], timeout=5).decode().strip()
        local_date = subprocess.check_output(["git", "-C", repo_dir, "log", "-1", "--pretty=%cd", "--date=format:%Y-%m-%d %H:%M"], timeout=5).decode().strip()
    except Exception as e:
        return {"success": False, "error": f"Gagal membaca info commit lokal: {e}"}

    remote_msg = ""
    remote_date = ""
    commits_behind = 0
    try:
        subprocess.run(["git", "-C", repo_dir, "fetch", "origin", "main"], timeout=20, check=True)
        remote_hash = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "origin/main"], timeout=5).decode().strip()
        remote_short = remote_hash[:7]
        remote_msg = subprocess.check_output(["git", "-C", repo_dir, "log", "-1", "--pretty=%s", "origin/main"], timeout=5).decode().strip()
        remote_date = subprocess.check_output(["git", "-C", repo_dir, "log", "-1", "--pretty=%cd", "--date=format:%Y-%m-%d %H:%M", "origin/main"], timeout=5).decode().strip()
        behind_str = subprocess.check_output(["git", "-C", repo_dir, "rev-list", "--count", "HEAD..origin/main"], timeout=5).decode().strip()
        commits_behind = int(behind_str) if behind_str.isdigit() else 0
    except Exception:
        try:
            ls_out = subprocess.check_output(["git", "ls-remote", "https://github.com/alijayanet/genieacs-multitab-mod.git", "refs/heads/main"], timeout=10).decode().strip()
            remote_hash = ls_out.split()[0] if ls_out else ""
            remote_short = remote_hash[:7]
        except Exception as e2:
            return {"success": False, "error": f"Gagal memeriksa GitHub: {e2}", "local_commit": local_short, "local_msg": local_msg, "local_date": local_date}

    has_update = bool(local_hash and remote_hash and local_hash != remote_hash)

    return {
        "success": True,
        "local_commit": local_short,
        "local_hash": local_hash,
        "local_msg": local_msg,
        "local_date": local_date,
        "remote_commit": remote_short,
        "remote_hash": remote_hash,
        "remote_msg": remote_msg or local_msg,
        "remote_date": remote_date or local_date,
        "commits_behind": commits_behind,
        "has_update": has_update
    }


def apply_system_update():
    repo_dirs = [
        "/root/genieacs-multitab-mod",
        "/opt/genieacs-multitab-mod",
        os.path.dirname(os.path.abspath(__file__))
    ]
    repo_dir = None
    for d in repo_dirs:
        if os.path.exists(os.path.join(d, ".git")):
            repo_dir = d
            break

    if not repo_dir:
        repo_dir = "/root/genieacs-multitab-mod"

    logs = []
    def log(msg):
        logs.append(msg)
        logger.info(f"[UPDATER] {msg}")

    try:
        log("🔄 [1/5] Mengambil pembaruan terbaru dari GitHub...")
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            cmd = subprocess.run(["git", "clone", "https://github.com/alijayanet/genieacs-multitab-mod.git", repo_dir], capture_output=True, text=True, timeout=40)
            if cmd.stdout.strip(): log(cmd.stdout.strip())
            if cmd.stderr.strip(): log(cmd.stderr.strip())
        else:
            cmd = subprocess.run(["git", "-C", repo_dir, "fetch", "origin", "main"], capture_output=True, text=True, timeout=25)
            if cmd.stdout.strip(): log(cmd.stdout.strip())
            if cmd.stderr.strip(): log(cmd.stderr.strip())
            cmd = subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "origin/main"], capture_output=True, text=True, timeout=10)
            if cmd.stdout.strip(): log(cmd.stdout.strip())
            if cmd.stderr.strip(): log(cmd.stderr.strip())

        log("📦 [2/5] Memperbarui script Agent (/opt/genieacs-agent/agent.py)...")
        src_agent = os.path.join(repo_dir, "agent.py")
        if os.path.exists(src_agent):
            import shutil
            shutil.copy2(src_agent, "/opt/genieacs-agent/agent.py")
            os.chmod("/opt/genieacs-agent/agent.py", 0o755)
            log("  ✓ agent.py berhasil diperbarui.")

        src_cli = os.path.join(repo_dir, "set-bot.py")
        if os.path.exists(src_cli):
            import shutil
            shutil.copy2(src_cli, "/usr/local/bin/set-bot")
            os.chmod("/usr/local/bin/set-bot", 0o755)
            log("  ✓ set-bot CLI berhasil diperbarui.")

        src_wa = os.path.join(repo_dir, "whatsapp", "whatsapp-bot.mjs")
        if not os.path.exists(src_wa):
            src_wa = os.path.join(repo_dir, "whatsapp-bot.mjs")
        if os.path.exists(src_wa):
            import shutil
            shutil.copy2(src_wa, "/opt/genieacs-agent/whatsapp-bot.mjs")
            os.chmod("/opt/genieacs-agent/whatsapp-bot.mjs", 0o755)
            log("  ✓ whatsapp-bot.mjs berhasil diperbarui.")

        log("🎨 [3/5] Memeriksa & memperbarui antarmuka GenieACS & Peta ODP...")
        tar_file = os.path.join(repo_dir, "genieacs_ui_mod.tar.gz")
        for node_dir in ["/usr/lib/node_modules", "/usr/local/lib/node_modules"]:
            genie_target = os.path.join(node_dir, "genieacs")
            if os.path.exists(genie_target):
                if os.path.exists(tar_file):
                    tar_cmd = subprocess.run(["tar", "-zxf", tar_file, "-C", node_dir + "/"], capture_output=True, text=True, timeout=30)
                    if tar_cmd.returncode == 0:
                        log(f"  ✓ genieacs_ui_mod.tar.gz diekstrak ke {node_dir}/.")
                pub = os.path.join(genie_target, "public")
                if os.path.exists(pub):
                    peta_src = os.path.join(repo_dir, "public", "peta.html")
                    app_src = os.path.join(repo_dir, "public", "app.js")
                    if os.path.exists(peta_src):
                        shutil.copy2(peta_src, os.path.join(pub, "peta.html"))
                        log("  ✓ peta.html berhasil diperbarui.")
                    if os.path.exists(app_src):
                        shutil.copy2(app_src, os.path.join(pub, "app.js"))
                        log("  ✓ app.js berhasil diperbarui.")

        # Update VirtualParameters (VlanID, pppoeUsername) & cache di MongoDB
        try:
            db = get_db()
            if db is not None:
                vp_vlan = db.virtualParameters.find_one({"_id": "VlanID"})
                if not vp_vlan:
                    vlan_script = 'let vlan = "-";\nlet p = declare("InternetGatewayDevice.WANDevice.1.WANConnectionDevice.*.WANPPPConnection.*.X_CT-COM_VlanID", {value: 1});\nif (p.value && p.value[0]) vlan = p.value[0];\nelse {\n  p = declare("InternetGatewayDevice.WANDevice.1.WANConnectionDevice.*.WANPPPConnection.*.X_CMCC_VLANIDMark", {value: 1});\n  if (p.value && p.value[0]) vlan = p.value[0];\n  else {\n    p = declare("InternetGatewayDevice.WANDevice.1.WANConnectionDevice.*.WANPPPConnection.*.X_HW_VLAN", {value: 1});\n    if (p.value && p.value[0]) vlan = p.value[0];\n    else {\n      p = declare("InternetGatewayDevice.WANDevice.1.WANConnectionDevice.*.WANPPPConnection.*.VLANID", {value: 1});\n      if (p.value && p.value[0]) vlan = p.value[0];\n    }\n  }\n}\nreturn {writable: true, value: [vlan, "xsd:string"]};'
                    db.virtualParameters.insert_one({"_id": "VlanID", "script": vlan_script})
                    log("  ✓ VirtualParameters.VlanID berhasil dibuat di MongoDB.")
                vp_user = db.virtualParameters.find_one({"_id": "pppoeUsername"})
                if vp_user and "writable: true" not in vp_user.get("script", ""):
                    new_script = vp_user.get("script", "").replace("return {writable: false", "return {writable: true")
                    db.virtualParameters.update_one({"_id": "pppoeUsername"}, {"$set": {"script": new_script}})
                    log("  ✓ VirtualParameters.pppoeUsername disetel writable di MongoDB.")
                db.config.delete_one({"_id": "ui-local-cache-hash"})
        except Exception as e_db:
            log(f"  ⚠️ MongoDB config update: {e_db}")

        log("🔄 [4/5] Me-restart service genieacs-ui...")
        subprocess.run(["systemctl", "restart", "genieacs-ui"], check=True, timeout=15)
        log("  ✓ genieacs-ui aktif.")

        try:
            subprocess.run(["systemctl", "try-restart", "genieacs-whatsapp"], timeout=10)
        except Exception:
            pass

        log("🚀 [5/5] Menjadwalkan restart service genieacs-agent dalam 2 detik...")
        subprocess.Popen(["bash", "-c", "sleep 2 && systemctl restart genieacs-agent"])
        log("  ✓ Selesai! Sistem akan memuat ulang halaman secara otomatis.")

        return {
            "success": True,
            "message": "Pembaruan berhasil diterapkan! Service sedang dimulai ulang.",
            "logs": "\n".join(logs)
        }
    except Exception as e:
        log(f"❌ Error saat update: {e}")
        return {
            "success": False,
            "error": str(e),
            "logs": "\n".join(logs)
        }



# ==============================================================================
# FITUR GEOLOCATION / MAPPING ODP & KLIEN (ALIJAYA NET)
# ==============================================================================

def get_geo_devices_data():
    db = get_db()
    if db is None:
        return {"success": False, "error": "Database tidak terhubung", "mapped": [], "unmapped": []}
    
    try:
        now_ts = time.time()
        loc_cursor = db.device_locations.find({})
        mapped_map = {}
        for doc in loc_cursor:
            dev_id = doc.get("_id")
            if dev_id:
                mapped_map[dev_id] = doc

        dev_cursor = db.devices.find({}, {
            "_id": 1,
            "_deviceId": 1,
            "_lastInform": 1,
            "_ip": 1,
            "VirtualParameters": 1,
            "InternetGatewayDevice.WANDevice": 1
        })

        mapped_list = []
        unmapped_list = []
        all_devices_dict = {}

        for dev in dev_cursor:
            dev_id = dev.get("_id")
            if not dev_id:
                continue
            all_devices_dict[dev_id] = dev

            pppoe = get_device_pppoe_username(dev)
            serial = dev.get("_deviceId", {}).get("_SerialNumber", "-")
            product_class = dev.get("_deviceId", {}).get("_ProductClass", "-")
            vp = dev.get("VirtualParameters", {})
            ip = (
                vp.get("pppoeIP", {}).get("_value") or
                vp.get("pppIP", {}).get("_value") or
                vp.get("IPTR069", {}).get("_value") or
                dev.get("_ip") or
                "-"
            )
            
            vp = dev.get("VirtualParameters", {})
            rx_raw = vp.get("RXPower", {}).get("_value")
            rx_val = None
            rx_str = "-"
            rx_status = "unknown"
            
            if rx_raw is not None and str(rx_raw).strip() not in ("", "-", "undefined", "null"):
                try:
                    cleaned_rx = str(rx_raw).replace("dBm", "").strip()
                    rx_val = round(float(cleaned_rx), 2)
                    rx_str = f"{rx_val} dBm"
                    if rx_val >= -24.0:
                        rx_status = "normal"
                    elif rx_val >= -27.0:
                        rx_status = "warning"
                    else:
                        rx_status = "critical"
                except Exception:
                    rx_str = str(rx_raw)

            last_inform = dev.get("_lastInform")
            is_online = False
            last_inform_str = "-"
            if last_inform:
                try:
                    diff_sec = get_datetime_diff_seconds(last_inform)
                    is_online = (diff_sec < 600)
                    if diff_sec < 60:
                        last_inform_str = "Baru saja"
                    elif diff_sec < 3600:
                        last_inform_str = f"{int(diff_sec // 60)} mnt lalu"
                    elif diff_sec < 86400:
                        last_inform_str = f"{int(diff_sec // 3600)} jam lalu"
                    else:
                        last_inform_str = f"{int(diff_sec // 86400)} hari lalu"
                except Exception:
                    pass

            if not is_online:
                rx_status = "offline"

            vlan_raw = vp.get("VlanID", {}).get("_value") or vp.get("vlan", {}).get("_value") or "-"
            dev_info = {
                "vlan": str(vlan_raw),
                "_id": dev_id,
                "pppoe": pppoe,
                "serial": serial,
                "product_class": product_class,
                "ip": ip,
                "rx": rx_str,
                "rx_val": rx_val,
                "rx_status": rx_status,
                "online": is_online,
                "last_inform": last_inform_str
            }

            if dev_id in mapped_map:
                loc_doc = mapped_map[dev_id]
                item = {
                    **dev_info,
                    "name": loc_doc.get("name") or pppoe,
                    "lat": float(loc_doc.get("lat", 0.0)),
                    "lng": float(loc_doc.get("lng", 0.0)),
                    "odp": loc_doc.get("odp", ""),
                    "phone": loc_doc.get("phone", ""),
                    "address": loc_doc.get("address", ""),
                    "notes": loc_doc.get("notes", ""),
                    "updated_at": loc_doc.get("updated_at", "")
                }
                mapped_list.append(item)
            else:
                unmapped_list.append(dev_info)

        for dev_id, loc_doc in mapped_map.items():
            if dev_id not in all_devices_dict:
                mapped_list.append({
                    "_id": dev_id,
                    "name": loc_doc.get("name", dev_id),
                    "pppoe": loc_doc.get("name", dev_id),
                    "serial": "-",
                    "product_class": "-",
                    "ip": "-",
                    "rx": "-",
                    "rx_val": None,
                    "rx_status": "offline",
                    "online": False,
                    "last_inform": "-",
                    "lat": float(loc_doc.get("lat", 0.0)),
                    "lng": float(loc_doc.get("lng", 0.0)),
                    "odp": loc_doc.get("odp", ""),
                    "phone": loc_doc.get("phone", ""),
                    "address": loc_doc.get("address", ""),
                    "notes": loc_doc.get("notes", ""),
                    "updated_at": loc_doc.get("updated_at", "")
                })

        return {
            "success": True,
            "mapped": mapped_list,
            "unmapped": unmapped_list,
            "total_mapped": len(mapped_list),
            "total_unmapped": len(unmapped_list)
        }
    except Exception as e:
        logger.error(f"Error getting geo devices data: {e}", exc_info=True)
        return {"success": False, "error": str(e), "mapped": [], "unmapped": []}


def save_geo_device_data(data):
    db = get_db()
    if db is None:
        return {"success": False, "message": "Database tidak terhubung"}
    
    dev_id = str(data.get("_id") or "").strip()
    if not dev_id:
        return {"success": False, "message": "ID Perangkat tidak boleh kosong"}
    
    try:
        lat = float(data.get("lat", 0.0))
        lng = float(data.get("lng", 0.0))
    except (ValueError, TypeError):
        return {"success": False, "message": "Koordinat Latitude / Longitude tidak valid"}

    doc = {
        "_id": dev_id,
        "name": str(data.get("name") or "").strip(),
        "lat": lat,
        "lng": lng,
        "odp": str(data.get("odp") or "").strip(),
        "phone": str(data.get("phone") or "").strip(),
        "address": str(data.get("address") or "").strip(),
        "notes": str(data.get("notes") or "").strip(),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        db.device_locations.update_one({"_id": dev_id}, {"$set": doc}, upsert=True)
        # Jika ada nomor HP, tambahkan juga tag otomatis ke ONU di GenieACS
        if doc.get("phone"):
            raw_ph = doc.get("phone").strip()
            digits = re.sub(r"\D", "", raw_ph)
            if len(digits) >= 8:
                add_device_tag(dev_id, raw_ph)
                if digits.startswith("0"):
                    add_device_tag(dev_id, "62" + digits[1:])
                elif digits.startswith("62"):
                    add_device_tag(dev_id, "0" + digits[2:])
        return {"success": True, "message": "Titik lokasi pelanggan berhasil disimpan", "data": doc}
    except Exception as e:
        logger.error(f"Error saving geo device {dev_id}: {e}", exc_info=True)
        return {"success": False, "message": f"Gagal menyimpan ke database: {e}"}


def delete_geo_device_data(dev_id):
    db = get_db()
    if db is None:
        return {"success": False, "message": "Database tidak terhubung"}
    
    if not dev_id:
        return {"success": False, "message": "ID Perangkat tidak boleh kosong"}
    
    try:
        res = db.device_locations.delete_one({"_id": dev_id})
        return {"success": True, "message": f"Lokasi pelanggan berhasil dihapus ({res.deleted_count})"}
    except Exception as e:
        return {"success": False, "message": f"Gagal menghapus: {e}"}


def get_geo_odps_data():
    db = get_db()
    if db is None:
        return {"success": False, "error": "Database tidak terhubung", "odps": []}
    
    try:
        odp_cursor = db.odp_locations.find({})
        odp_list = []
        for doc in odp_cursor:
            odp_id = doc.get("_id")
            if not odp_id:
                continue
            
            used = db.device_locations.count_documents({"odp": odp_id})
            cap = int(doc.get("capacity", 8))
            
            odp_list.append({
                "_id": odp_id,
                "name": doc.get("name") or odp_id,
                "lat": float(doc.get("lat", 0.0)),
                "lng": float(doc.get("lng", 0.0)),
                "capacity": cap,
                "color": doc.get("color", "#3b82f6"),
                "notes": doc.get("notes", ""),
                "used_ports": used,
                "available_ports": max(0, cap - used),
                "updated_at": doc.get("updated_at", "")
            })
            
        return {"success": True, "odps": odp_list}
    except Exception as e:
        logger.error(f"Error getting geo ODPs: {e}", exc_info=True)
        return {"success": False, "error": str(e), "odps": []}


def save_geo_odp_data(data):
    db = get_db()
    if db is None:
        return {"success": False, "message": "Database tidak terhubung"}
    
    odp_id = str(data.get("_id") or "").strip().upper()
    if not odp_id:
        count = db.odp_locations.count_documents({}) + 1
        odp_id = f"ODP-ALJ-{count:02d}"
    
    try:
        lat = float(data.get("lat", 0.0))
        lng = float(data.get("lng", 0.0))
    except (ValueError, TypeError):
        return {"success": False, "message": "Koordinat Latitude / Longitude tidak valid"}

    doc = {
        "_id": odp_id,
        "name": str(data.get("name") or odp_id).strip(),
        "lat": lat,
        "lng": lng,
        "capacity": int(data.get("capacity", 8)),
        "color": str(data.get("color") or "#3b82f6").strip(),
        "notes": str(data.get("notes") or "").strip(),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.odp_locations.update_one({"_id": odp_id}, {"$set": doc}, upsert=True)
        return {"success": True, "message": f"Data {odp_id} berhasil disimpan", "data": doc}
    except Exception as e:
        logger.error(f"Error saving ODP {odp_id}: {e}", exc_info=True)
        return {"success": False, "message": f"Gagal menyimpan ODP: {e}"}


def delete_geo_odp_data(odp_id):
    db = get_db()
    if db is None:
        return {"success": False, "message": "Database tidak terhubung"}
    
    if not odp_id:
        return {"success": False, "message": "ID ODP tidak boleh kosong"}
    
    try:
        res = db.odp_locations.delete_one({"_id": odp_id})
        db.device_locations.update_many({"odp": odp_id}, {"$set": {"odp": ""}})
        return {"success": True, "message": f"ODP {odp_id} berhasil dihapus"}
    except Exception as e:
        return {"success": False, "message": f"Gagal menghapus ODP: {e}"}


class BotConfigHandler(BaseHTTPRequestHandler):
    def parse_cookies(self):
        cookie_header = self.headers.get("Cookie", "")
        cookies = {}
        if cookie_header:
            for c in cookie_header.split(";"):
                if "=" in c:
                    k, v = c.strip().split("=", 1)
                    cookies[k.strip()] = v.strip()
        return cookies

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.end_headers()

    def is_authenticated_admin(self):
        client_ip = self.client_address[0] if self.client_address else ""
        # Localhost bypass specifically for bot internal webhook
        parsed_path = urlparse(self.path).path
        # Localhost bypass specifically for bot internal service-to-service communication
        if client_ip in ("127.0.0.1", "::1", "localhost") and not self.headers.get("X-Forwarded-For") and parsed_path in ("/api/agent_command", "/api/config"):
            return True

        cookies = self.parse_cookies()

        # Check 1: SSO via GenieACS UI JWT cookie
        jwt_cookie = cookies.get("genieacs-ui-jwt")
        if jwt_cookie:
            payload = verify_genieacs_jwt(jwt_cookie)
            if payload and payload.get("username"):
                username = payload.get("username")
                db = get_db()
                if db is not None:
                    u = db.users.find_one({"_id": username})
                    if u:
                        roles = [r.strip() for r in u.get("roles", "").split(",") if r.strip()]
                        if "admin" in roles:
                            return True

        # Check 2: Direct session cookie on port 7558
        sess_token = cookies.get("agent_session")
        if sess_token and sess_token in ACTIVE_ADMIN_SESSIONS:
            sess_data = ACTIVE_ADMIN_SESSIONS[sess_token]
            if sess_data.get("expires", 0) > time.time():
                return True
            else:
                ACTIVE_ADMIN_SESSIONS.pop(sess_token, None)

        return False

    def send_html(self, content_str, status=200, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "frame-ancestors 'self' http://*:3000 https://*:3000 http://* https://*")
        if extra_headers:
            for hk, hv in extra_headers.items():
                self.send_header(hk, hv)
        self.end_headers()
        self.wfile.write(content_str.encode("utf-8"))

    def send_json(self, data, status=200, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra_headers:
            for hk, hv in extra_headers.items():
                self.send_header(hk, hv)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Jalur Akses Peta & API Geolocation (Bebas CORS & Iframe)
        if path in ("/peta", "/peta.html"):
            peta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "peta.html")
            if not os.path.exists(peta_path):
                for cand in [
                    "/usr/lib/node_modules/genieacs/public/peta.html",
                    "/usr/local/lib/node_modules/genieacs/public/peta.html",
                    "/opt/genieacs/public/peta.html"
                ]:
                    if os.path.exists(cand):
                        peta_path = cand
                        break
            if os.path.exists(peta_path):
                try:
                    with open(peta_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.send_html(content)
                    return
                except Exception as e:
                    self.send_html(f"<h3>Gagal memuat peta: {e}</h3>", status=500)
                    return
            else:
                self.send_html("<h3>File peta.html belum tersedia</h3>", status=404)
                return

        if path == "/api/geo/devices":
            data = get_geo_devices_data()
            self.send_json(data)
            return

        if path == "/api/geo/odps":
            data = get_geo_odps_data()
            self.send_json(data)
            return
        if not self.is_authenticated_admin():
            if self.path == "/" or self.path.startswith("/?"):
                self.send_html(HTML_LOGIN_PAGE)
            else:
                self.send_json({"success": False, "error": "Akses ditolak: Harap login sebagai administrator terlebih dahulu."}, status=401)
            return

        if self.path == "/" or self.path.startswith("/?"):
            self.send_html(HTML_CONFIG_PAGE)
        elif self.path == "/api/config":
            cfgs = get_config()
            data = {
                "enabled": cfgs.get("agent.enabled", "true"),
                "token": cfgs.get("agent.telegram.botToken", ""),
                "admin_id": cfgs.get("agent.telegram.adminChatId", ""),
                "brand_name": cfgs.get("agent.brand.name", BRAND_NAME),
                "brand_phone": cfgs.get("agent.brand.phone", BRAND_PHONE),
                "gemini_key": cfgs.get("agent.gemini.apiKey", ""),
                "wa_enabled": cfgs.get("agent.whatsapp.enabled", "true"),
                "wa_admin_numbers": cfgs.get("agent.whatsapp.admin_numbers", cfgs.get("agent.brand.phone", BRAND_PHONE))
            }
            self.send_json(data)
        elif self.path == "/api/whatsapp/status":
            try:
                r = requests.get("http://127.0.0.1:7559/status", timeout=5.0)
                self.send_json(r.json())
            except Exception as e:
                self.send_json({"connection": "disconnected", "error": str(e)})
        elif self.path == "/api/whatsapp/lid_mappings":
            try:
                r = requests.get("http://127.0.0.1:7559/lid_mappings", timeout=2.5)
                self.send_json(r.json())
            except Exception as e:
                self.send_json({"error": str(e)})
        elif self.path == "/api/system/update_status":
            st = get_system_update_status()
            self.send_json(st)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        try:
            req = json.loads(body)
        except Exception:
            req = {}

        parsed = urlparse(self.path)
        path = parsed.path

        # Endpoint API Geolocation Pelanggan & ODP
        if path == "/api/wan/set":
            dev_id = req.get("device_id") or req.get("_id") or req.get("id")
            pppoe_user = req.get("pppoe_user") or req.get("username", "")
            pppoe_pass = req.get("pppoe_pass") or req.get("password", "")
            vlan_id = req.get("vlan_id") or req.get("vlan")

            if not dev_id:
                self.send_json({"success": False, "message": "ID Perangkat tidak boleh kosong"})
                return
            if not pppoe_user:
                self.send_json({"success": False, "message": "Username PPPoE tidak boleh kosong"})
                return

            dev = find_device(dev_id)
            if not dev:
                self.send_json({"success": False, "message": f"Modem `{dev_id}` tidak ditemukan di database"})
                return

            ok, msg = add_or_set_wan_pppoe(dev, pppoe_user, pppoe_pass, vlan_id)
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/geo/device":
            res = save_geo_device_data(req)
            self.send_json(res)
            return

        if path == "/api/geo/device/delete":
            dev_id = req.get("_id") or req.get("id")
            res = delete_geo_device_data(dev_id)
            self.send_json(res)
            return

        if path == "/api/geo/odp":
            res = save_geo_odp_data(req)
            self.send_json(res)
            return

        if path == "/api/geo/odp/delete":
            odp_id = req.get("_id") or req.get("id")
            res = delete_geo_odp_data(odp_id)
            self.send_json(res)
            return

        # Public authentication endpoints
        if self.path == "/api/login":
            username = req.get("username", "").strip()
            password = req.get("password", "").strip()
            ok, msg = verify_admin_login(username, password)
            if ok:
                token = secrets.token_hex(32)
                ACTIVE_ADMIN_SESSIONS[token] = {
                    "username": username,
                    "expires": time.time() + 86400  # 24 hours
                }
                cookie_val = f"agent_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400"
                self.send_json({"success": True, "message": "Login berhasil"}, extra_headers={"Set-Cookie": cookie_val})
            else:
                self.send_json({"success": False, "message": msg}, status=401)
            return

        elif self.path == "/api/logout":
            cookies = self.parse_cookies()
            tok = cookies.get("agent_session")
            if tok in ACTIVE_ADMIN_SESSIONS:
                ACTIVE_ADMIN_SESSIONS.pop(tok, None)
            cookie_val = "agent_session=deleted; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            self.send_json({"success": True, "message": "Logout berhasil"}, extra_headers={"Set-Cookie": cookie_val})
            return

        # Check authentication for all protected endpoints
        if not self.is_authenticated_admin():
            self.send_json({"success": False, "error": "Akses ditolak: Harap login sebagai administrator terlebih dahulu."}, status=401)
            return

        if self.path == "/api/config":
            db = get_db()
            if db is None:
                self.send_json({"success": False, "message": "Gagal terhubung ke MongoDB"})
                return

            configs_to_save = {
                "agent.enabled": req.get("enabled", "true"),
                "agent.telegram.botToken": f'"{req.get("token", "").strip()}"',
                "agent.telegram.adminChatId": f'"{req.get("admin_id", "").strip()}"',
                "agent.brand.name": f'"{req.get("brand_name", BRAND_NAME).strip()}"',
                "agent.brand.phone": f'"{req.get("brand_phone", BRAND_PHONE).strip()}"',
                "agent.gemini.apiKey": f'"{req.get("gemini_key", "").strip()}"',
                "agent.whatsapp.enabled": f'"{req.get("wa_enabled", "true").strip()}"',
                "agent.whatsapp.admin_numbers": f'"{req.get("wa_admin_numbers", BRAND_PHONE).strip()}"'
            }

            for k, v in configs_to_save.items():
                db.config.update_one({"_id": k}, {"$set": {"value": v}}, upsert=True)

            # Immediately update in-memory branding variables in agent.py
            update_branding(get_config())
            try:
                wa_payload = {
                    "brand_name": BRAND_NAME,
                    "brand_phone": BRAND_PHONE,
                    "wa_admin_numbers": req.get("wa_admin_numbers", BRAND_PHONE).strip()
                }
                requests.post("http://127.0.0.1:7559/reload_admins", json=wa_payload, timeout=2.0)
            except Exception as e:
                logger.warning(f"Failed to notify WhatsApp service: {e}")

            logger.info("Konfigurasi bot berhasil disimpan melalui Web UI (Port 7558)!")
            self.send_json({"success": True, "message": "Konfigurasi berhasil disimpan"})

        elif self.path == "/api/system/update_apply":
            res = apply_system_update()
            self.send_json(res)
        elif self.path in ["/api/whatsapp/logout", "/api/whatsapp/reset"]:
            try:
                requests.post("http://127.0.0.1:7559/logout", timeout=4.0)
            except Exception:
                pass

            auth_dirs = [
                "/opt/genieacs-agent/auth_info_baileys",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_info_baileys")
            ]
            for ad in auth_dirs:
                if os.path.exists(ad):
                    try:
                        import shutil
                        shutil.rmtree(ad, ignore_errors=True)
                    except Exception:
                        pass

            try:
                import subprocess
                subprocess.run(["systemctl", "restart", "genieacs-whatsapp.service"], check=False)
            except Exception:
                pass

            self.send_json({"success": True, "message": "Sesi WhatsApp berhasil dihapus dan bot direset"})

        elif self.path == "/api/agent_command":
            text = req.get("text", "")
            sender = req.get("sender", "anonymous")
            is_admin = bool(req.get("isAdmin", False))
            push_name = req.get("pushName", "")
            reg_tag = req.get("registeredTag", None)

            cfgs = get_config()
            gemini_key = cfgs.get("agent.gemini.apiKey", "")
            gemini_model = cfgs.get("agent.gemini.model", "gemini-1.5-flash")

            try:
                reply_text, _ = process_agent_command(
                    user_text=text,
                    sender_id=sender,
                    is_admin=is_admin,
                    gemini_key=gemini_key,
                    gemini_model=gemini_model,
                    registered_tag=reg_tag
                )
                self.send_json({"success": True, "reply": reply_text})
            except Exception as e:
                logger.error(f"Error handling agent_command '{text}': {e}", exc_info=True)
                self.send_json({"success": False, "reply": f"⚠️ Terjadi error internal saat memproses perintah `{text}`: {e}"})

        elif self.path == "/api/test":
            token = req.get("token", "").strip()
            admin_id = req.get("admin_id", "").strip()
            if not token or not admin_id:
                self.send_json({"success": False, "message": "Token dan Chat ID tidak boleh kosong!"})
                return

            ids = parse_admin_chat_ids(admin_id)
            test_msg = f"🧪 *Tes Notifikasi Bot GenieACS*\n━━━━━━━━━━━━━━━━━━━━\nKoneksi berhasil! Bot siap digunakan ({BRAND_NAME})."
            success_count = 0
            err_msg = ""
            for aid in ids:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                try:
                    r = requests.post(url, json={"chat_id": aid, "text": test_msg, "parse_mode": "Markdown"}, timeout=8)
                    if r.status_code == 200:
                        success_count += 1
                    else:
                        err_msg = r.text
                except Exception as e:
                    err_msg = str(e)

            if success_count > 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "message": err_msg})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def start_web_server(port=7558):
    try:
        server = DefaultHTTPServer(("0.0.0.0", port), BotConfigHandler)
        logger.info(f"Bot Web Config UI berjalan di http://0.0.0.0:{port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Gagal menjalankan Bot Web Config server di port {port}: {e}")

def main():
    logger.info("Starting ALIJAYA NET GenieACS AI Agent Service...")
    web_thread = threading.Thread(target=start_web_server, args=(7558,), daemon=True)
    web_thread.start()
    last_update_id = 0
    notified_online = False
    last_watchdog_time = 0
    
    while True:
        try:
            cfgs = get_config()
            update_branding(cfgs)
            enabled = cfgs.get("agent.enabled", "true").lower() == "true"
            token = cfgs.get("agent.telegram.botToken", "")
            admin_cfg_str = cfgs.get("agent.telegram.adminChatId", "")
            admin_ids = parse_admin_chat_ids(admin_cfg_str)
            gemini_key = cfgs.get("agent.gemini.apiKey", "")
            gemini_model = cfgs.get("agent.gemini.model", "gemini-1.5-flash")
            
            if not enabled:
                logger.info("Agent is disabled in config (agent.enabled=false). Sleeping...")
                time.sleep(30)
                continue
                
            if not is_valid_token(token):
                logger.info("Menunggu konfigurasi token Telegram di GenieACS Web UI (Admin -> Config)...")
                time.sleep(15)
                continue
                
            if not notified_online:
                register_bot_commands(token)
                greeting = (
                    f"🚀 *{BRAND_NAME} GenieACS Bot Aktif!*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Menu interaktif, audit redaman, deteksi ONT baru & kontrol TR-069 siap melayani.\n"
                    "Ketik `/menu` atau klik tombol di bawah untuk mulai."
                )
                for aid in admin_ids:
                    send_telegram(token, aid, greeting, reply_markup=get_main_menu_keyboard())
                notified_online = True
                logger.info(f"Bot Telegram berhasil terhubung dan siap melayani ({BRAND_NAME})!")

            # Periodic Watchdog (setiap 60 detik)
            now = time.time()
            if (now - last_watchdog_time) >= 60:
                check_proactive_alerts(token, admin_ids)
                last_watchdog_time = now

            # Poll Telegram Updates
            poll_url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=15"
            r = requests.get(poll_url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                for upd in data.get("result", []):
                    last_update_id = upd.get("update_id", last_update_id)
                    
                    cb = upd.get("callback_query")
                    if cb:
                        cb_id = cb.get("id")
                        cb_sender = str(cb.get("from", {}).get("id", ""))
                        cb_data = cb.get("data", "")
                        if admin_ids and not is_authorized(cb_sender, admin_ids):
                            answer_callback(token, cb_id, f"Akses ditolak! Bukan Admin/Teknisi {BRAND_NAME}.", show_alert=True)
                            continue
                        handle_callback_query(token, cb_sender, cb_data, cb_id)
                        continue

                    msg = upd.get("message", {})
                    chat = msg.get("chat", {})
                    sender_id = str(chat.get("id", ""))
                    text = msg.get("text", "")
                    
                    if admin_ids and not is_authorized(sender_id, admin_ids):
                        logger.warning(f"Unauthorized chat from {sender_id}: {text}")
                        send_telegram(token, sender_id, f"⛔ Akses Ditolak: ID Anda ({sender_id}) bukan Admin/Teknisi {BRAND_NAME}.")
                        continue
                        
                    if text:
                        logger.info(f"Received command: '{text}' from {sender_id}")
                        handle_incoming_message(token, sender_id, text, gemini_key, gemini_model)
            else:
                logger.warning(f"Telegram polling returned HTTP {r.status_code}")
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
