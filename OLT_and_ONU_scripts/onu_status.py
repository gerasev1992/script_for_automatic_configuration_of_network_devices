import sys
import re
import ctypes
import asyncio
import psycopg2

from pysnmp.hlapi.v3arch.asyncio import *

DB_CONFIG = {
    "host": "your_ip_address",
    "port": 5432,
    "database": "your_db",
    "user": "your_user",
    "password": "your_password"
}

SNMP_CONFIG = {
    "community": "your_community",
    "timeout": 2,
    "retries": 1
}

def show_message(text, title="ONU Info", icon=0x40):
    try:
        ctypes.windll.user32.MessageBoxW(0, str(text), title, icon)
    except Exception:
        print(text)

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        show_message(f"Ошибка подключения к БД:\n\n{e}", "ONU Info - ошибка")
        return None

async def _snmp_get(ip, community, oid):
    try:
        error_indication, error_status, error_index, var_binds = await get_cmd(
            SnmpEngine(),
            CommunityData(community),
            await UdpTransportTarget.create(
                (ip, 161),
                timeout=SNMP_CONFIG["timeout"],
                retries=SNMP_CONFIG["retries"]
            ),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        if error_indication:
            err_text = str(error_indication).lower()

            if "timed out" in err_text or "timeout" in err_text:
                return "HOST UNREACHABLE"

            return f"SNMP ERROR: {error_indication}"

        if error_status:
            return f"SNMP ERROR: {error_status.prettyPrint()}"

        if not var_binds:
            return "NO DATA"

        value = str(var_binds[0][1]).strip()

        if value == "1":
            return "UP"

        if value == "2":
            return "DOWN"

        return value

    except Exception as e:
        err_text = str(e).lower()

        if "timed out" in err_text or "timeout" in err_text:
            return "HOST UNREACHABLE"

        return f"ERROR: {e}"

def snmp_get(ip, oid):
    if not ip:
        return "NO LTE IP"

    if not oid:
        return "NO OID"

    try:
        return asyncio.run(
            _snmp_get(
                ip,
                SNMP_CONFIG["community"],
                oid
            )
        )
    except Exception as e:
        return f"ERROR: {e}"

def get_current_client_lan_status(ip, ifindex):
    if not ifindex:
        return "NO IFINDEX"

    oid = f".1.3.6.1.4.1.3320.10.4.9.1.3.{ifindex}.1"
    return snmp_get(ip, oid)

def search_onu(search_value):
    search_value = search_value.strip()

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        if re.match(r"^HWTC", search_value, re.IGNORECASE):
            clean_value = search_value.upper()

            query = """
                SELECT
                    hwtc_serial,
                    onu_name,
                    lte_ip,
                    onu_status,
                    onu_up_down_time,
                    gpon_port,
                    onu_rxpower,
                    lte_rxpower,
                    onu_client_vlan,
                    onu_lan_status,
                    onu_client_mac,
                    snmp_gpon_port_group,
                    snmp_gpon_port_index,
                    snmp_gpon_port_onu_index,
                    onu_snmp_status_oid,
                    last_seen
                FROM public.onu_status
                WHERE hwtc_serial = %s
                ORDER BY last_seen DESC
                LIMIT 1
            """
            cursor.execute(query, (clean_value,))

        else:
            query = """
                SELECT
                    hwtc_serial,
                    onu_name,
                    lte_ip,
                    onu_status,
                    onu_up_down_time,
                    gpon_port,
                    onu_rxpower,
                    lte_rxpower,
                    onu_client_vlan,
                    onu_lan_status,
                    onu_client_mac,
                    snmp_gpon_port_group,
                    snmp_gpon_port_index,
                    snmp_gpon_port_onu_index,
                    onu_snmp_status_oid,
                    last_seen
                FROM public.onu_status
                WHERE onu_name = %s
                ORDER BY last_seen DESC
                LIMIT 1
            """
            cursor.execute(query, (search_value,))

        row = cursor.fetchone()

        cursor.close()
        conn.close()

        return row

    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass

        show_message(f"Ошибка поиска:\n\n{e}", "ONU Info - ошибка")
        return None

def format_vlan_mac(vlans, macs):
    if not vlans and not macs:
        return "N/A"

    vlan_list = [v.strip() for v in str(vlans or "").split(",") if v.strip()]
    mac_list = [m.strip() for m in str(macs or "").split(",") if m.strip()]

    max_len = max(len(vlan_list), len(mac_list))
    lines = []

    for i in range(max_len):
        vlan = vlan_list[i] if i < len(vlan_list) else "N/A"
        mac = mac_list[i] if i < len(mac_list) else "N/A"
        lines.append(f"{vlan} | {mac}")

    return "\n".join(lines)

def format_output(row, search_value):
    if not row:
        show_message(
            f"По запросу ничего не найдено:\n\n{search_value}",
            "ONU Search"
        )
        return

    (
        hwtc_serial,
        onu_name,
        lte_ip,
        onu_status,
        onu_up_down_time,
        gpon_port,
        onu_rxpower,
        lte_rxpower,
        onu_client_vlan,
        onu_lan_status,
        onu_client_mac,
        snmp_gpon_port_group,
        snmp_gpon_port_index,
        snmp_gpon_port_onu_index,
        onu_snmp_status_oid,
        last_seen
    ) = row

    onu_current_client_lan_status = get_current_client_lan_status(
        lte_ip,
        snmp_gpon_port_onu_index
    )

    onu_current_status = snmp_get(lte_ip, onu_snmp_status_oid)

    rx_str = f"{onu_rxpower:.1f}" if onu_rxpower is not None else "N/A"
    lte_str = f"{lte_rxpower:.1f}" if lte_rxpower is not None else "N/A"
    last_seen_str = last_seen.strftime("%H:%M:%S %d-%m-%Y") if last_seen else "N/A"
    vlan_mac_str = format_vlan_mac(onu_client_vlan, onu_client_mac)

    if onu_current_status == "UP":
        title = "[UP] ONU Info"
        icon = 0x40  # Information

    elif onu_current_status == "DOWN":
        title = "[DOWN] ONU Info"
        icon = 0x10  # Error

    else:
        title = f"[{onu_current_status}] ONU Info"
        icon = 0x30  # Warning

    text = (
        f"ONU Name: {onu_name or 'N/A'}\n"
        f"HWTC: {hwtc_serial or 'N/A'}\n\n"
        f"LTE IP: {lte_ip or 'N/A'}\n"
        f"GPON port: {gpon_port or 'N/A'}\n\n"
        f"Status: {onu_status or 'N/A'}\n"
        f"Status Time: {onu_up_down_time or 'N/A'}\n\n"
        f"ONU RxPower: {rx_str or 'N/A'} dBm\n"
        f"LTE RxPower: {lte_str or 'N/A'} dBm\n\n"
#        f"Client LAN Status: {onu_lan_status or 'N/A'}\n\n"
        f"Client vlan | mac-addr:\n"
        f"{vlan_mac_str}\n\n"
        f"Updated: {last_seen_str}\n\n"
        "----------------------------------\n"
        f"Current Client LAN Status: {onu_current_client_lan_status or 'N/A'}\n\n"
        f"Current ONU Status: {onu_current_status or 'N/A'}\n"
    )

    show_message(text, title, icon)

def main():
    if len(sys.argv) < 2:
        show_message(
            'Не передан параметр.\n\n'
            'Примеры:\n'
            'onu_info.exe "HWTC:XXXXXXXX"\n'
            'onu_info.exe "your_ip_address"',
            "ONU Info - ошибка"
        )
        sys.exit(1)

    search_input = " ".join(sys.argv[1:]).strip()

    row = search_onu(search_input)
    format_output(row, search_input)


if __name__ == "__main__":
    main()
