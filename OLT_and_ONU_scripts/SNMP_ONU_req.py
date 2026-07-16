import subprocess
import os
import re
import asyncio
import gc
import sys
import json
import signal
from datetime import datetime
import time

# ========== ПОДКЛЮЧЕНИЕ К POSTGRESQL ==========
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2 import sql
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("psycopg2 не установлен. Установите: pip install psycopg2")
# =============================================

# Получаем путь к папке, где находится .exe
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# Скрытие окон для Windows
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# Список IP-адресов для опроса
IP_LIST = [
    "your_ip_address",
]

# Специальные IP с особыми OID
SPECIAL_HOSTS = [
    "your_ip_address",
]

SPECIAL_COMMUNITY = "your_community"

# Стандартные OID для обычных устройств
DEFAULT_CONFIG = {
    'start_oid_6': '.1.3.6.1.4.1.3320.10.2.6.1.6.110.0',
    'stop_oid_6': '.1.3.6.1.4.1.3320.10.2.6.1.6.117.8192',
    'start_oid_3': '.1.3.6.1.4.1.3320.10.2.6.1.3.110.0',
    'stop_oid_3': '.1.3.6.1.4.1.3320.10.2.6.1.3.117.8192',
    'start_oid_port': '.1.3.6.1.2.1.2.2.1.8.109',
    'stop_oid_port': '.1.3.6.1.2.1.2.2.1.8.8192',
    'start_oid_vlan': '.1.3.6.1.4.1.3320.10.9.3.1.4.110.118.108.97.110.95.97.99.99.101.115.115',
    'stop_oid_vlan': '.1.3.6.1.4.1.3320.10.9.3.1.4.117.118.108.97.110.95.97.99.99.101.115.115.8192.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0',
    'start_oid_rxpower': '.1.3.6.1.4.1.3320.10.3.4.1.2.0',
    'stop_oid_rxpower': '.1.3.6.1.4.1.3320.10.3.4.1.2.8192',
    'start_oid_lte_rxpower': '.1.3.6.1.4.1.3320.10.2.3.1.3.0',
    'stop_oid_lte_rxpower': '.1.3.6.1.4.1.3320.10.2.3.1.3.8192',
    'start_oid_client_mac': '.1.3.6.1.2.1.17.7.1.2.2.1.2.0',
    'stop_oid_client_mac': '.1.3.6.1.2.1.17.7.1.2.2.1.2.8192'
}

# Специальные OID для SPECIAL_HOSTS
SPECIAL_CONFIG = {
    'start_oid_6': '.1.3.6.1.4.1.3320.10.2.6.1.6.105.0',
    'stop_oid_6': '.1.3.6.1.4.1.3320.10.2.6.1.6.117.8192',
    'start_oid_3': '.1.3.6.1.4.1.3320.10.2.6.1.3.105.0',
    'stop_oid_3': '.1.3.6.1.4.1.3320.10.2.6.1.3.117.8192',
    'start_oid_port': '.1.3.6.1.2.1.2.2.1.8.0',
    'stop_oid_port': '.1.3.6.1.2.1.2.2.1.8.8192',
    'start_oid_vlan': '.1.3.6.1.4.1.3320.10.9.3.1.4.105.118.108.97.110.95.97.99.99.101.115.115',
    'stop_oid_vlan': '.1.3.6.1.4.1.3320.10.9.3.1.4.117.118.108.97.110.95.97.99.99.101.115.115.8192.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0',
    'start_oid_rxpower': '.1.3.6.1.4.1.3320.10.3.4.1.2.0',
    'stop_oid_rxpower': '.1.3.6.1.4.1.3320.10.3.4.1.2.8192',
    'start_oid_lte_rxpower': '.1.3.6.1.4.1.3320.10.2.3.1.3.0',
    'stop_oid_lte_rxpower': '.1.3.6.1.4.1.3320.10.2.3.1.3.8192',
    'start_oid_client_mac': '.1.3.6.1.2.1.17.7.1.2.2.1.2.0',
    'stop_oid_client_mac': '.1.3.6.1.2.1.17.7.1.2.2.1.2.8192'
}

COMMUNITY = "your_community"

# ========== ПАРАМЕТРЫ ПОДКЛЮЧЕНИЯ К БД ==========
DB_CONFIG = {
    'host': 'your_ip_address',
    'port': 5432,
    'database': 'your_db,
    'user': 'your_user',
    'password': 'your_password'
}
# ===============================================

# Используем относительные пути
COMBINED_REPORT_FILENAME = os.path.join(BASE_DIR, "snmp_OLT_full_ONU.txt")
TIMERS_FILE = os.path.join(BASE_DIR, "onu_timers.json")
SNMPWALK_PATH = os.path.join(BASE_DIR, "SnmpWalk.exe")

# ========== НАСТРОЙКИ ОПТИМИЗАЦИИ ==========
POLL_INTERVAL = 90
MAX_CONCURRENT_HOSTS = 2
SNMP_TIMEOUT = 60
REQUEST_DELAY = 0.3
BATCH_SIZE = 3
# ===========================================

_shutdown_flag = False

def signal_handler(signum, frame):
    global _shutdown_flag
    _shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_db_connection():
    """Создает подключение к PostgreSQL"""
    if not POSTGRES_AVAILABLE:
        return None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        return None

def format_rxpower(value):
    """Преобразует значение RxPower в дБм с одним десятичным знаком"""
    try:
        val = int(value)
        dbm = val / 10.0
        return f"{dbm:.1f}"
    except:
        return "N/A"

def format_lte_rxpower(value):
    """Преобразует значение LTE RxPower в дБм с одним десятичным знаком"""
    try:
        val = int(value)
        dbm = val / 10.0
        return f"{dbm:.1f}"
    except:
        return "N/A"

def save_to_database(all_results):
    """Сохраняет результаты в PostgreSQL"""
    if not POSTGRES_AVAILABLE:
        return False
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        current_time = datetime.now()
        
        for res in all_results:
            if res.get('error') or not res.get('data'):
                continue
            
            host = res['host']
            is_special = (host in SPECIAL_HOSTS)
            
            for item in res['data']:
                # HWTC с префиксом
                hwtc_serial = f"HWTC:{item['value3']}"
                
                # Имя ONU (из VLAN описания или IP)
                onu_name = item.get('vlan_description', 'N/A')
                if onu_name == 'N/A' or onu_name == '':
                    onu_name = host
                
                # Статус и время
                onu_status = item.get('port_status', 'UNKNOWN')
                onu_up_down_time = item.get('duration_formatted', '0с')
                gpon_port = f"{convert_group_to_port_name(item['group'], is_special)}:{item['index']}"
                
                # GPON Rx Power
                rxpower_str = item.get('rxpower', 'N/A')
                try:
                    onu_rxpower = float(rxpower_str) if rxpower_str != 'N/A' else None
                except:
                    onu_rxpower = None
                
                # LTE Rx Power
                lte_rxpower_str = item.get('lte_rxpower', 'N/A')
                try:
                    lte_rxpower = float(lte_rxpower_str) if lte_rxpower_str != 'N/A' else None
                except:
                    lte_rxpower = None
                
                # Client MAC/VLAN - сохраняем как строки (VARCHAR/TEXT)
                client_vlan_raw = item.get('client_vlan', 'N/A')
                client_mac_raw = item.get('client_mac', 'N/A')
                
                # Для VARCHAR/TEXT колонок: оставляем строку или NULL
                if client_vlan_raw != 'N/A' and client_vlan_raw != '':
                    onu_client_vlan = client_vlan_raw
                else:
                    onu_client_vlan = None
                
                # Для VARCHAR колонки: оставляем строку или NULL
                if client_mac_raw != 'N/A' and client_mac_raw != '':
                    onu_client_mac = client_mac_raw
                else:
                    onu_client_mac = None

                # LTE IP
                lte_ip = host
                
                # SNMP индексы
                snmp_gpon_port_group = int(item['group']) if item['group'].isdigit() else None
                snmp_gpon_port_index = int(item['index']) if item['index'].isdigit() else None
                snmp_gpon_port_onu_index = int(item['value6']) if item['value6'].isdigit() else None
                
                # Формируем OID для статуса
                if snmp_gpon_port_onu_index is not None:
                    onu_snmp_status_oid = f".1.3.6.1.2.1.2.2.1.8.{snmp_gpon_port_onu_index}"
                else:
                    onu_snmp_status_oid = None
                
                # UPSERT запрос
                query = """
                    INSERT INTO public.onu_status (
                        hwtc_serial, onu_name, onu_status, onu_up_down_time,
                        gpon_port, onu_rxpower, lte_rxpower,
                        snmp_gpon_port_group, snmp_gpon_port_index, snmp_gpon_port_onu_index,
                        onu_snmp_status_oid,
                        lte_ip,
                        onu_client_vlan, onu_client_mac,
                        last_seen, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s,
                        %s,
                        %s, %s,
                        %s, %s
                    ) ON CONFLICT (hwtc_serial) DO UPDATE SET
                        onu_name = EXCLUDED.onu_name,
                        onu_status = EXCLUDED.onu_status,
                        onu_up_down_time = EXCLUDED.onu_up_down_time,
                        gpon_port = EXCLUDED.gpon_port,
                        onu_rxpower = EXCLUDED.onu_rxpower,
                        lte_rxpower = EXCLUDED.lte_rxpower,
                        snmp_gpon_port_group = EXCLUDED.snmp_gpon_port_group,
                        snmp_gpon_port_index = EXCLUDED.snmp_gpon_port_index,
                        snmp_gpon_port_onu_index = EXCLUDED.snmp_gpon_port_onu_index,
                        onu_snmp_status_oid = EXCLUDED.onu_snmp_status_oid,
                        lte_ip = EXCLUDED.lte_ip,
                        onu_client_vlan = EXCLUDED.onu_client_vlan,
                        onu_client_mac = EXCLUDED.onu_client_mac,
                        last_seen = EXCLUDED.last_seen,
                        updated_at = EXCLUDED.updated_at
                """
                
                cursor.execute(query, (
                    hwtc_serial,
                    onu_name,
                    onu_status,
                    onu_up_down_time,
                    gpon_port,
                    onu_rxpower,
                    lte_rxpower,
                    snmp_gpon_port_group,
                    snmp_gpon_port_index,
                    snmp_gpon_port_onu_index,
                    onu_snmp_status_oid,
                    lte_ip,
                    onu_client_vlan,
                    onu_client_mac,
                    current_time,
                    current_time
                ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False

def save_combined_results(all_results):
    """Сохраняет результаты в файл (резервный вариант)"""
    with open(COMBINED_REPORT_FILENAME, "w", encoding="utf-8") as f:
        f.write(f"{'ХОСТ':<16} {'ГРУППА':<8} {'ИНДЕКС':<8} {'ПОРТ':<6} {'HEX':<20} {'СТАТУС':<8} {'ОПИСАНИЕ':<20} {'GPON ПОРТ':<15} {'ВРЕМЯ':<15} {'GPON Rx(dBм)':<15} {'LTE Rx(dBм)':<15} {'LTE IP':<16} {'VLAN':<8} {'MAC':<20} {'OID СТАТУСА':<30}\n")
        f.write("-" * 275 + "\n")
        
        for res in all_results:
            if res.get('error'):
                f.write(f"{res['error']}\n\n")
            elif res.get('data'):
                host = res['host']
                is_special = (host in SPECIAL_HOSTS)
                for item in res['data']:
                    desc = item.get('vlan_description', 'N/A')
                    gpon = f"{convert_group_to_port_name(item['group'], is_special)}:{item['index']}"
                    duration = item.get('duration_formatted', '0с')
                    rxpower = item.get('rxpower', 'N/A')
                    lte_rxpower = item.get('lte_rxpower', 'N/A')
                    client_vlan = item.get('client_vlan', 'N/A')
                    client_mac = item.get('client_mac', 'N/A')
                    port_num = item.get('value6', '')
                    status_oid = f".1.3.6.1.2.1.2.2.1.8.{port_num}" if port_num else 'N/A'
                    f.write(f"{host:<16} {item['group']:<8} {item['index']:<8} {item['value6']:<6} HWTC:{item['value3']:<17} {item['port_status']:<8} {desc:<20} {gpon:<15} {duration:<15} {rxpower:<15} {lte_rxpower:<15} {host:<16} {client_vlan:<8} {client_mac:<20} {status_oid:<30}\n")
                f.write("\n")
            else:
                f.write("Нет данных\n\n")

def load_timers():
    try:
        if os.path.exists(TIMERS_FILE):
            with open(TIMERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_timers(timers):
    try:
        os.makedirs(os.path.dirname(TIMERS_FILE), exist_ok=True)
        with open(TIMERS_FILE, "w", encoding="utf-8") as f:
            json.dump(timers, f, separators=(',', ':'))
    except Exception:
        pass

def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m{s}s" if s else f"{m}m"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h{m}m" if m else f"{h}h"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}d{h}h" if h else f"{d}d"

def update_timers(current_data, current_time):
    timers = load_timers()
    updated = False
    
    for device in current_data:
        if not device.get('data'):
            continue
        
        host = device['host']
        for onu in device['data']:
            key = f"{host}_{onu['group']}_{onu['index']}"
            current_state = onu['port_status']
            
            if key not in timers:
                timers[key] = {"s": current_state, "t": 0, "u": current_time}
                updated = True
            else:
                old_state = timers[key]["s"]
                old_seconds = timers[key]["t"]
                last_update = timers[key]["u"]
                
                try:
                    last = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
                    now = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
                    elapsed = int((now - last).total_seconds())
                except:
                    elapsed = POLL_INTERVAL
                
                if old_state == current_state:
                    timers[key]["t"] = old_seconds + elapsed
                else:
                    timers[key]["s"] = current_state
                    timers[key]["t"] = 0
                    updated = True
                
                timers[key]["u"] = current_time
            
            onu['duration'] = timers[key]["t"]
            onu['duration_formatted'] = format_duration(timers[key]["t"])
    
    if updated:
        save_timers(timers)
    
    return timers

async def run_snmpwalk_async(host, community, start_oid, stop_oid):
    if not os.path.exists(SNMPWALK_PATH):
        return None, None
    
    cmd = [SNMPWALK_PATH, f"-r:{host}", "-v:2c", f"-c:{community}", 
           f"-os:{start_oid}", f"-op:{stop_oid}"]
    
    try:
        startupinfo = None
        creationflags = 0
        
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
        
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=SNMP_TIMEOUT,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        
        if result.returncode == 0:
            return result.stdout, result.returncode
        return None, result.returncode
            
    except subprocess.TimeoutExpired:
        return None, -1
    except Exception:
        return None, -1

def parse_snmp_output_standard(output):
    if not output:
        return {}
    
    results = {}
    lines = output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('SnmpWalk') or line.startswith('[ More useful'):
            continue
        
        oid_match = re.search(r'OID=([^,]+)', line)
        value_match = re.search(r'Value=([^,]+)$', line)
        
        if oid_match and value_match:
            oid = oid_match.group(1)
            value = value_match.group(1)
            oid_parts = oid.split('.')
            
            if len(oid_parts) >= 14:
                group = oid_parts[13]
                index = oid_parts[14] if len(oid_parts) > 14 else "0"
                key = f"{group}.{index}"
                if 'HWTC:' in value:
                    hex_match = re.search(r'HWTC:([A-F0-9]+)', value)
                    if hex_match:
                        value = hex_match.group(1)
                results[key] = value
    
    return results

def parse_snmp_output_rxpower(output):
    """Парсит вывод RxPower OID в словарь {порт: значение дБм}"""
    results = {}
    if not output:
        return results
    
    lines = output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('SnmpWalk') or line.startswith('[ More useful'):
            continue
        
        oid_match = re.search(r'OID=([^,]+)', line)
        value_match = re.search(r'Value=([^,]+)$', line)
        
        if oid_match and value_match:
            oid = oid_match.group(1)
            value = value_match.group(1)
            oid_parts = oid.split('.')
            
            if len(oid_parts) >= 14:
                port_num = str(oid_parts[13])
                results[port_num] = format_rxpower(value)
    
    return results

def parse_snmp_output_lte_rxpower(output):
    """Парсит вывод LTE RxPower OID в словарь {порт: значение дБм}"""
    results = {}
    if not output:
        return results
    
    lines = output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('SnmpWalk') or line.startswith('[ More useful'):
            continue
        
        oid_match = re.search(r'OID=([^,]+)', line)
        value_match = re.search(r'Value=([^,]+)$', line)
        
        if oid_match and value_match:
            oid = oid_match.group(1)
            value = value_match.group(1)
            oid_parts = oid.split('.')
            
            if len(oid_parts) >= 14:
                port_num = str(oid_parts[-1])
                results[port_num] = format_lte_rxpower(value)
    
    return results

def parse_snmp_output_port(output):
    if not output:
        return {}
    
    results = {}
    for line in output.split('\n'):
        line = line.strip()
        if not line or line.startswith('SnmpWalk') or line.startswith('[ More useful'):
            continue
        
        oid_match = re.search(r'OID=([^,]+)', line)
        value_match = re.search(r'Value=([^,]+)$', line)
        
        if oid_match and value_match:
            oid_parts = oid_match.group(1).split('.')
            if len(oid_parts) >= 12:
                port_num = oid_parts[11]
                value = value_match.group(1)
                status = 'UP' if value == '1' else 'DOWN' if value == '2' else value
                results[port_num] = status
    
    return results

def parse_snmp_output_client_mac(output):
    """
    Парсит вывод OID .1.3.6.1.2.1.17.7.1.2.2.1.2.*
    Формат: OID=.1.3.6.1.2.1.17.7.1.2.2.1.2.VLAN.MAC, Type=Integer, Value=ONU_INDEX
    Пример: OID=.1.3.6.1.2.1.17.7.1.2.2.1.2.3031.164.186.112.192.98.16, Type=Integer, Value=220
    Возвращает: {onu_index: [{'vlan': vlan, 'mac_dec': mac_dec, 'mac_hex': mac_hex}, ...]}
    """
    results = {}
    if not output:
        return results
    
    lines = output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('SnmpWalk') or line.startswith('[ More useful'):
            continue
        
        oid_match = re.search(r'OID=([^,]+)', line)
        value_match = re.search(r'Value=([^,]+)$', line)
        
        if oid_match and value_match:
            oid = oid_match.group(1)
            onu_index = value_match.group(1).strip()
            
            oid_parts = oid.split('.')
            
            for i in range(len(oid_parts) - 6):
                if (oid_parts[i] == '1' and 
                    oid_parts[i+1] == '2' and 
                    oid_parts[i+2] == '2' and 
                    oid_parts[i+3] == '1' and 
                    oid_parts[i+4] == '2'):
                    
                    start_idx = i + 5
                    if start_idx < len(oid_parts):
                        vlan = oid_parts[start_idx]
                        mac_dec_parts = oid_parts[start_idx + 1:]
                        
                        if not mac_dec_parts:
                            continue
                        
                        mac_hex_parts = []
                        valid_mac = True
                        for dec_part in mac_dec_parts:
                            try:
                                dec_val = int(dec_part)
                                if 0 <= dec_val <= 255:
                                    hex_val = format(dec_val, '02X')
                                    mac_hex_parts.append(hex_val)
                                else:
                                    valid_mac = False
                                    break
                            except ValueError:
                                valid_mac = False
                                break
                        
                        if valid_mac and mac_hex_parts:
                            mac_hex = ':'.join(mac_hex_parts)
                            mac_dec = '.'.join(mac_dec_parts)
                            
                            if onu_index not in results:
                                results[onu_index] = []
                            
                            results[onu_index].append({
                                'vlan': vlan,
                                'mac_dec': mac_dec,
                                'mac_hex': mac_hex
                            })
                        break
    
    return results

def decode_vlan_port(encoding_parts):
    if not encoding_parts:
        return []
    
    ports = []
    for i, part in enumerate(encoding_parts):
        try:
            value = int(part)
            if value != 0:
                for exp in range(8):
                    if 2**exp == value:
                        ports.append(str(i * 8 + (8 - exp)))
                        break
        except (ValueError, TypeError):
            continue
    
    return ports if ports else None

def parse_snmp_output_vlan(output, is_special=False):
    if not output:
        return {}
    
    results = {}
    if is_special:
        valid_groups = ['105', '106', '107', '108', '109', '110', '111', '112', '113', '114', '115', '116', '117']
    else:
        valid_groups = ['110', '111', '112', '113', '114', '115', '116', '117']
    
    for line in output.split('\n'):
        line = line.strip()
        if not line or line.startswith('SnmpWalk') or line.startswith('[ More useful'):
            continue
        
        oid_match = re.search(r'OID=([^,]+)', line)
        value_match = re.search(r'Value=([^,]+)$', line)
        
        if oid_match and value_match:
            oid = oid_match.group(1)
            value = value_match.group(1)
            oid_parts = oid.split('.')
            
            for i, part in enumerate(oid_parts):
                if part in valid_groups:
                    group = part
                    encoding_parts = []
                    found = False
                    
                    for j in range(i + 1, len(oid_parts)):
                        try:
                            num = int(oid_parts[j])
                            if num == 0 or (num & (num - 1)) == 0:
                                encoding_parts.append(str(num))
                                found = True
                            elif found:
                                break
                        except ValueError:
                            if found:
                                break
                    
                    if encoding_parts:
                        port_numbers = decode_vlan_port(encoding_parts)
                        if port_numbers:
                            ip_match = re.search(r'\d+\.\d+\.\d+\.\d+$', value)
                            if ip_match:
                                description = ip_match.group(0)
                            else:
                                parts = value.split(' ', 1)
                                description = parts[1] if len(parts) > 1 else value
                            
                            for port_num in port_numbers:
                                key = f"{group}.{port_num}"
                                if key not in results:
                                    results[key] = description
                    break
    
    return results

def compare_results(results_type6, results_type3):
    matches = []
    for key in (set(results_type6) & set(results_type3)):
        g, i = key.split('.')
        matches.append({'group': g, 'index': i, 'value6': results_type6[key], 'value3': results_type3[key]})
    return matches

def merge_with_port_status(matches, port_status):
    for m in matches:
        m['port_status'] = port_status.get(str(m['value6']), 'UNKNOWN')
    return matches

def merge_with_vlan(vlan_results, merged):
    for item in merged:
        item['vlan_description'] = vlan_results.get(f"{item['group']}.{item['index']}", 'N/A')
    return merged

def convert_group_to_port_name(group, is_special=False):
    if is_special:
        group_map = {
            '105': 'gpon0/0', '106': 'gpon0/1', '107': 'gpon0/2', 
            '108': 'gpon0/3', '109': 'gpon0/4', '110': 'gpon0/5', 
            '111': 'gpon0/6', '112': 'gpon0/7', '113': 'gpon0/8',
            '114': 'gpon0/9', '115': 'gpon0/10', '116': 'gpon0/11', 
            '117': 'gpon0/12'
        }
    else:
        group_map = {
            '110': 'gpon0/1', '111': 'gpon0/2', '112': 'gpon0/3',
            '113': 'gpon0/4', '114': 'gpon0/5', '115': 'gpon0/6',
            '116': 'gpon0/7', '117': 'gpon0/8'
        }
    return group_map.get(group, f'unknown{group}')

async def process_host_async(host, semaphore, is_special=False):
    async with semaphore:
        config = SPECIAL_CONFIG if is_special else DEFAULT_CONFIG
        community = SPECIAL_COMMUNITY if is_special else COMMUNITY
        
        out6, code = await run_snmpwalk_async(host, community, config['start_oid_6'], config['stop_oid_6'])
        if not out6:
            return {'host': host, 'data': None, 'error': f'Ошибка SNMP, код: {code}', 'timestamp': datetime.now().isoformat()}
        
        results6 = parse_snmp_output_standard(out6)
        
        await asyncio.sleep(REQUEST_DELAY)
        
        results = await asyncio.gather(
            run_snmpwalk_async(host, community, config['start_oid_3'], config['stop_oid_3']),
            run_snmpwalk_async(host, community, config['start_oid_port'], config['stop_oid_port']),
            run_snmpwalk_async(host, community, config['start_oid_vlan'], config['stop_oid_vlan']),
            run_snmpwalk_async(host, community, config['start_oid_rxpower'], config['stop_oid_rxpower']),
            run_snmpwalk_async(host, community, config['start_oid_lte_rxpower'], config['stop_oid_lte_rxpower']),
            run_snmpwalk_async(host, community, config['start_oid_client_mac'], config['stop_oid_client_mac'])
        )
        
        results3 = parse_snmp_output_standard(results[0][0]) if results[0][0] else {}
        port_status = parse_snmp_output_port(results[1][0]) if results[1][0] else {}
        vlan_results = parse_snmp_output_vlan(results[2][0], is_special) if results[2][0] else {}
        rxpower_results = parse_snmp_output_rxpower(results[3][0]) if results[3][0] else {}
        lte_rxpower_results = parse_snmp_output_lte_rxpower(results[4][0]) if results[4][0] else {}
        client_mac_results = parse_snmp_output_client_mac(results[5][0]) if results[5][0] else {}
        
        matches = compare_results(results6, results3)
        
        if not matches:
            return {'host': host, 'data': None, 'error': 'Совпадений не найдено', 'timestamp': datetime.now().isoformat()}
        
        merged = merge_with_port_status(matches, port_status)
        merged = merge_with_vlan(vlan_results, merged)
        
        EXCLUDED_VLANS = ['9', '11']
        
        for item in merged:
            onu_index = str(item['value6'])
            
            item['rxpower'] = rxpower_results.get(onu_index, 'N/A')
            item['lte_rxpower'] = lte_rxpower_results.get(onu_index, 'N/A')
            
            if onu_index in client_mac_results:
                client_list = client_mac_results[onu_index]
                    
                if client_list:
                    filtered_clients = [c for c in client_list if c.get('vlan') not in EXCLUDED_VLANS]
                        
                    if filtered_clients:
                        all_vlans = ','.join([c.get('vlan', '') for c in filtered_clients if c.get('vlan')])
                        item['client_vlan'] = all_vlans if all_vlans else 'N/A'
                            
                        all_macs = ','.join([c.get('mac_hex', '') for c in filtered_clients if c.get('mac_hex')])
                        item['client_mac'] = all_macs if all_macs else 'N/A'
                    else:
                        item['client_vlan'] = 'N/A'
                        item['client_mac'] = 'N/A'
                else:
                    item['client_vlan'] = 'N/A'
                    item['client_mac'] = 'N/A'
            else:
                item['client_vlan'] = 'N/A'
                item['client_mac'] = 'N/A'
        
        return {'host': host, 'data': merged, 'timestamp': datetime.now().isoformat()}

async def main_async():
    global _shutdown_flag
    
    if _shutdown_flag:
        return
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_HOSTS)
    all_results = []
    
    # 1. Опрашиваем специальные хосты
    for special_host in SPECIAL_HOSTS:
        special_result = await process_host_async(special_host, semaphore, is_special=True)
        if special_result and special_result.get('data'):
            all_results.append(special_result)
    
    # 2. Опрашиваем остальные хосты
    for i in range(0, len(IP_LIST), BATCH_SIZE):
        if _shutdown_flag:
            break
        batch = IP_LIST[i:i+BATCH_SIZE]
        tasks = [process_host_async(ip, semaphore, is_special=False) for ip in batch]
        batch_results = await asyncio.gather(*tasks)
        all_results.extend(batch_results)
        gc.collect()
    
    if all_results:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_timers(all_results, current_time)
        
        db_success = save_to_database(all_results)
        
        await asyncio.to_thread(save_combined_results, all_results)
        
        if db_success:
            print(f"Данные сохранены в PostgreSQL")

async def run_periodically_async():
    global _shutdown_flag
    
    iteration = 1
    while not _shutdown_flag:
        try:
            start_time = datetime.now()
            
            await main_async()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\nИтерация #{iteration} завершена за {elapsed:.1f} сек")
            
            for _ in range(POLL_INTERVAL):
                if _shutdown_flag:
                    break
                await asyncio.sleep(1)
            
            iteration += 1
            
        except Exception as e:
            await asyncio.sleep(10)

def run_periodically():
    print("Для остановки нажмите Ctrl+C")
    
    try:
        asyncio.run(run_periodically_async())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        time.sleep(5)
        run_periodically()

if __name__ == "__main__":
    run_periodically()
