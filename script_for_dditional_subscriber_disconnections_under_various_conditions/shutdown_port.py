from netmiko import ConnectHandler
import re
import time
import pickle
import time
import sys
from datetime import datetime, timedelta

files = {
    "vars.pkl": {"keys": ["ip_address", "port_number"], "required": True},
    "vars_kv.pkl": {"keys": ["kvartira"], "required": True},
    "vars_date.pkl": {"keys": ["date"], "required": False},
    "vars_down.pkl": {"keys": ["down"], "required": False},
    "vars_req.pkl": {"keys": ["req"], "required": False},
}
data = {}
for filename, config in files.items():
    try:
        with open(filename, "rb") as f:
            file_data = pickle.load(f)
            for key in config["keys"]:
                data[key] = file_data[key]
    except FileNotFoundError:
        if config["required"]:
            print(f"Ошибка: {filename} не найден.")
            exit(1)
        else:
            print(f"Файл {filename} не найден. Пропускаем...")
            for key in config["keys"]:
                data[key] = None
# Извлекаем переменные
ip_address = data["ip_address"]
port_number = data["port_number"]
kvartira = data["kvartira"]
date = data.get("date")
down = data.get("down")
req = data.get("req")
# Используем переменные
print(f"ip_address = {ip_address}")
print(f"port_number = {port_number}")
print(f"kvartira = {kvartira}")
print(f"date = {date}")
print(f"down = {down}")
print(f"request = {req}")
# Текущая дата
current_date = datetime.now()
formatted_date = current_date.strftime("%d.%m.%Y")
print(f'\n{formatted_date}')
if date is not None:
    date_obj = datetime.strptime(date, "%d.%m.%Y")
else:
    date_obj = None
if date == None:
    date_obj = None
else:
    date_obj = datetime.strptime(date, "%d.%m.%Y")
if date_obj == None:
    date_plus_one  = None
else:
    date_plus_one = date_obj + timedelta(days=1)   

if date is not None and formatted_date >= date and down == "Отключение" and req != "по заявлению":
    print(f"\ndown = {down} Даты совпадают")
    print (f'Дата в наряде: {date}')
    print (f'Сегодня: {formatted_date}') 
    print (f'Отключение') 
else: 
    (date is None or formatted_date != date or date >= formatted_date) and (down == "Отключение" or down == None) and (req == "по заявлению" or req == None)
    if date == None:
        print("Дата выполнения наряда неизвестна")
    else:    
        print(f'Выполните наряд на отключение {date_plus_one}')
        print(f'Сегодня: {formatted_date}')
    print("\nПродолжить выполнение?")
    user_input_date = input("Ваш выбор (y/n): ").strip()
    print(user_input_date)
    if user_input_date.lower() == 'y':
        print("Продолжаем")
    else:
        print("Завершено")
        sys.exit(0)  
print("\n" + "="*60)
ip = ip_address
# ip = input("Введите IP-адрес устройства (или 'quit' для выхода): ").strip()
if ip.lower() == 'quit':
    print("Выход из программы.")
    sys.exit(0)
if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
    print("Некорректный IP-адрес. Попробуйте снова.")
    #continue
#    host_ip = input("Введите IP-адрес хоста: ").strip()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ИНТЕРАКТИВНЫЙ ВЫБОР ПОРТОВ ---
def select_ports(port_list, model_name):
    if not port_list:
        print("Нет портов для выбора.")
        return []
    print("\n" + "="*60)
    print(f"Доступные порты для {model_name}:")
    print("="*60)
    for i, port in enumerate(port_list, 1):
        print(f"{i:2d}. {port}")
    print("\nВведите номера портов через запятую (например: 1,3,5) или 'all' для всех:")
    user_input = port_number
    # user_input = input("Ваш выбор: ").strip()
    if user_input.lower() == 'all':
        selected = port_list.copy()
    else:
        try:
            indices = []
            for item in user_input.split(','):
                item = item.strip()
                if '-' in item:  # Поддержка диапазонов: 1-3
                    start, end = map(int, item.split('-'))
                    indices.extend(range(start-1, end))
                elif item.isdigit():
                    indices.append(int(item) - 1)
            selected = [port_list[i] for i in indices if 0 <= i < len(port_list)]
        except (ValueError, IndexError):
            print("Некорректный ввод. Выбрано ничего.")
            selected = []
    if selected:
        print(f"\nВыбрано портов: {len(selected)}")
        for port in selected:
            print(f"   {port}")
    else:
        print("Не выбрано ни одного порта.")
    return selected

# --- ОСНОВНАЯ ФУНКЦИЯ: ПОДКЛЮЧЕНИЕ И АНАЛИЗ ---
def main():
    # === ПАРАМЕТРЫ ПОДКЛЮЧЕНИЯ ===
    device = {
        'device_type': 'cisco_ios',  # или 'cisco_ios_telnet', если используется Telnet
        'host': ip,       # Замените на ваш IP
        'username': 'USERNAME',         # Замените на ваш логин
        'password': 'PASSWORD',      # Замените на ваш пароль
        #'secret': 'enable_password', # Пароль enable (если нужен)
        'timeout': 10,
        'global_delay_factor': 2,
    }
    device_unknown = {
        'device_type': 'dlink_ds',  # или 'cisco_ios_telnet', если используется Telnet
        'host': ip,       # Замените на ваш IP
        'username': 'USERNAME',         # Замените на ваш логин
        'password': 'PASSWORD',      # Замените на ваш пароль
        #'secret': 'enable_password', # Пароль enable (если нужен)
        'timeout': 10,
        'global_delay_factor': 2,
    }        
    connection = ConnectHandler(**device)
    try:
        print(f"Подключение к устройству {ip}")
        connection
        # Входим в enable
        print("Вход в enable...")
        connection.enable()
        # Определяем модель устройства
        print("Определение модели...")
        output_version = connection.send_command("show version", delay_factor=2)
        if "Zy" in output_version:
            model = "Zy"
            print(f"Обнаружена модель {model}") 
        elif "5210" in output_version:
            model = "5210"
            print(f"Обнаружена модель {model}")
        elif "Cisco" in output_version:
            model = "Cisco"
            print(f"Обнаружена модель {model}")       
        elif "29" in output_version:
            model = "29"
            print(f"Обнаружена модель {model}")
        else:
            print("Неизвестная модель. Попробуем продолжить...")
            model = "unknown"
          
        #ZY
        if model == "Zy":
            flat_zy = (f"kv{kvartira}")
            port_input = port_number
            # input("Введите номер порта:").strip()#port_number
            print(port_input)
            print("\nВыполняем 'show int conf '...")
            output_int_brief = connection.send_command(f"show int conf {port_input}", delay_factor=2)
            print(f"Вывод:\n{output_int_brief}\n")
            match_vl = re.search(r'\b(?:XXXX|3[1-9]\d{2})\b', output_int_brief)
            if match_vl:
                match_vlan = match_vl.group()
                print(f"Номер vlan: {match_vlan}")
            else:
                print("Номер vlan not XXXX and not 31xx")
                match_vlan = None
            print("\nВыполняем 'show interfaces '...")
            output_int_brief_si = connection.send_command_timing(f"show interfaces {port_input}")
            time.sleep(5)
            print(f"Вывод:\n{output_int_brief_si}\n")
            Active = re.search(r'\bLink\s*:\s*Down\b', output_int_brief_si)
            if Active:
                link_state = Active.group()
                print(f"Active: {link_state}")
            else:
                print("Up")
                link_state = None
            print("\nВыполняем 'sh mac address-table port '...")
            output_int_brief1 = connection.send_command(f"sh mac address-table port {port_input}", delay_factor=2)
            print(f"Вывод:\n{output_int_brief1}\n")
            # if "XXXX" in output_int_brief:
            match = re.search(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}[\.\-]){2}[0-9A-Fa-f]{4}\b|\b[0-9A-Fa-f]{12}\b', output_int_brief1)
            if match:
                macaca = match.group()
                print(f"MAC-адрес найден: {macaca}")
                print("\n" + "="*60)
                print(f'"Проверьте сессию абонента PPPoE ses={macaca} или если DHCP-абонента mfses={macaca}"')
                print("="*60)
            else:
                print("MAC-адрес не найден")
                macaca = None
                print("\nВыполняем 'show running-config interface port-channel'...")
                output_int_brief3 = connection.send_command_timing(f"show running-config interface port-channel {port_input}")
                time.sleep(5)
                print(f"Вывод:\n{output_int_brief3}\n")
            if match_vlan is not None and str(match_vlan) in output_int_brief3 and (f"fixed {port_input}") in output_int_brief3 and match_vlan in output_int_brief and macaca == None and "Down" in link_state:  # ← Теперь mac_address всегда инициализирована
                print(f"Условия выполнены: vlan={match_vlan}, mac={macaca}, down/up={link_state} Отключаем порт")
                time.sleep(2)               
            else:
                print(f"Условия не выполнены: vlan={match_vlan}, mac={macaca}, down/up={link_state}")
                if macaca != None:
                    print("\nВнести изменения принудительно?")
                    user_input1 = input("Ваш выбор: ").strip()
                    print(user_input1)
                    if user_input1.lower() == 'y':
                        # flat_zy = (f'kv{kvartira}')
                        # input("Введите номер квартиру, например (kv94):").strip()
                        print(flat_zy)
                        should_process = True
                    else:
                        print("Завершена работа")
                        sys.exit(0)                         
                else:
                    print("Завершена работа")
                    sys.exit(0)  
                # Отправляем конфигурационные команды с явным указанием промпта
            print("\nВнести изменения для данного порта?")
            user_input1 = input("Ваш выбор: ").strip()
            print(user_input1)
            if user_input1.lower() == 'y':
                try:
                    # Сначала переходим в режим конфигурации
                    connection.enable()
                    connection.config_mode()  # Входим в режим конфигурации
                    # Выполняем команды по одной с явным ожиданием промпта
                    commands = [
                        f"vlan {match_vlan}",
                        f"forbidden {port_input}",
                        f"exit",
                        f"interface port-channel {port_input}",
                        f"pvid 1",
                        f"name free_{flat_zy}",
                        f"inactive",
                        f"exit",
                        f"exit",
                    ] 
                    for cmd in commands:
                        print(f"Отправка команды: {cmd}")
                        output = connection.send_command_timing(
                            cmd,
                            delay_factor=3,
                            strip_prompt=False,
                            strip_command=False
                        )
                        print(f"Ответ: {output[:100]}...")  # Печатаем первые 100 символов вывода
                        time.sleep(1)
                    print("\nВыполняем 'write memory'...")
                    output_int_brief5 = connection.send_command_timing(f"write memory")
                    time.sleep(10)
                    print(f"Вывод:\n{output_int_brief5}\n") 
                    print("\nВыполняем 'show int conf '...")
                    output_int_brief = connection.send_command(f"show int conf {port_input}", delay_factor=2)
                    print(f"Вывод:\n{output_int_brief}\n")
                    print(f"Успешно: interface {port_input} Отключен")
                except Exception as e:
                    print(f"Ошибка конфигурации: {e}")
                    # Выходим из режима конфигурации
                    connection.disconnect()
            else:
                # Обычная обработка: показываем MAC и инфо
                if macaca:
                    print(f"MAC-таблица:")
                else:
                    print("MAC-таблица: пуста")

                print(f"Информация о порте:\n ")
                # Показываем, почему не сработало
                if not (match_vlan and macaca and link_state):
                    print(f"Условия не выполнены")

        # === ОБРАБОТКА МОДЕЛИ 5210 ===
        elif model == "5210":
            print("\nВыполняем 'show int brief'...")
            output_int_brief = connection.send_command("show int brief", delay_factor=2)
            print(f"Вывод:\n{output_int_brief}\n")
            # Извлекаем порты в формате geX/X, xeX/X
            ports_with_prefix = []
            for line in output_int_brief.splitlines():
                line = line.strip()
                if not line or any(header in line for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                    continue
                match = re.search(r'^(ge\d+|xe\d+)', line)
                if match:
                    port = match.group(1)
                    ports_with_prefix.append(port)
            ports_with_prefix = list(dict.fromkeys(ports_with_prefix))  # Уникальные, сохраняя порядок
            print(f"Извлеченные порты (с префиксом ge/xe): {ports_with_prefix}\n")
            # Интерактивный выбор портов
            selected_ports = select_ports(ports_with_prefix, model)
            # Обработка каждого выбранного порта
            for port in selected_ports:
                print(f"\nОбработка порта: {port}")
                #Проверка MAC-адресов
                print(f"   show mac address-table interface {port}")
                try:
                    output_mac = connection.send_command(f"show mac address-table interface {port}")
                    print(f"{output_mac}\n")
                    match = re.search(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}[\.\-]){2}[0-9A-Fa-f]{4}\b|\b[0-9A-Fa-f]{12}\b',output_mac)
                    if match:
                        macaca = match.group()
                        print(f"MAC-адрес найден: {macaca}\n")
                        print("\n" + "="*60)
                        print(f'Проверьте сессию абонента PPPoE ses={macaca} или если DHCP-абонента mfses={macaca}')
                        print("="*60)                      
                    else:
                        print("MAC-адрес не найден")
                        macaca = None                           
                except Exception as e:
                    print(f"Ошибка MAC: {e}")
                #Проверка состояния порта из show int brief
                port_info_line = None
                for line in output_int_brief.splitlines():
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    if any(header in line_clean for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                        continue
                    if line_clean.startswith(port + " ") or f" {port} " in line_clean:
                        port_info_line = line_clean
                        break
                print(port_info_line)
                match_vl = re.search(r'\b(?:XXXX|3[1-9]\d{2})\b', port_info_line)
                if match_vl:
                    match_vlan = match_vl.group()
                    print(f"Номер vlan: {match_vlan}")
                else:
                    print("Номер vlan not XXXX and not 31xx")
                    match_vlan = None
                if not port_info_line:
                    print(f"Не найдена строка порта в show int brief: {port}")
                    continue
                # Проверяем условия: access, YYYY, down
                is_access = "access" in port_info_line.lower()
                has_vlan_YYYY = "YYYY" in port_info_line
                is_down = "down" in port_info_line.lower()
                is_up = "up" in port_info_line.lower()              
                condition_met = False
                vlan_to_use = ""
                # Условие для автоматического описания
                should_process = False
                flat_input1 = (f"kv{kvartira}")
                if is_access and has_vlan_YYYY and (is_down or is_up) and macaca == None:
                    print(f"Условия выполнены: access={is_access}, vYYYY={has_vlan_YYYY}, down={is_down}, up={is_up}")
                    output_sh_run_int_start = connection.send_command(f"show run int {port}")
                    print(output_sh_run_int_start)
                    condition_met = True
                    vlan_to_use = "ZZZZ"  # Для первого условия используем vlan ZZZZ
                elif is_access and match_vlan != None and (is_down or is_up) and macaca == None:
                    print(f"Условия выполнены: vlan={match_vlan}, down={is_down}, mac={macaca}, up={is_up}, access={is_access}")
                    output_sh_run_int_start = connection.send_command(f"show run int {port}")
                    print(output_sh_run_int_start)
                    condition_met = True
                    vlan_to_use = "1"  # Для первого условия используем vlan 1                    
                else:
                    print(f"Условия не выполнены: vYYYY={has_vlan_YYYY}, vlan={match_vlan}, down={is_down}, mac={macaca}, up={is_up}, access={is_access}")                    
                    if is_access != True:
                        print('PORT TRUNK')
                        break  
                    if match_vlan == None:
                        vlan_to_use = "ZZZZ"
                    else: vlan_to_use = "1"
                    print(vlan_to_use)     
                    if macaca != None:
                        print("\nВнести изменения принудительно?")
                        user_input1 = input("Ваш выбор: ").strip()
                        print(user_input1)  
                        if user_input1.lower() == 'y':
                            # flat_input1 = (f"kvartira")
                            print(flat_input1)
                            should_process = True
                            condition_met = True
                        else:
                            print("Завершена работа")
                            break
                    else:
                        print("Завершена работа")
                        break
                # Если условие выполнено (if или elif), продолжаем обработку
                if condition_met:
                    # Проверяем, определена ли flat_input1, если нет - запрашиваем
                    if not 'flat_input1' in locals() or not flat_input1:
                        flat_input1 = (f"kvartira")
                        print(flat_input1)                 
                    print("\nВнести изменения для данного порта?")
                    user_input1 = input("Ваш выбор: ").strip()
                    print(user_input1)    
                    if user_input1.lower() == 'y':
                        try:
                            # Входим в конфигурационный режим
                            # Используем vlan_to_use который определили ранее (ZZZZ или 1)
                            connection.send_config_set([
                                f"interface {port}",
                                f"description free_{flat_input1}",
                                f"switch access vlan {vlan_to_use}",
                                f"shutdown",
                                f"exit",
                                f"exit",
                                f"write"
                            ], delay_factor=2)
                            output_sh_run_int = connection.send_command(f"show run int {port}")
                            print(output_sh_run_int)
                            print(f"Успешно: interface {port} Отключен")
                        except Exception as e:
                            print(f"Ошибка конфигурации: {e}")
                else:
                    # Обычная обработка: показываем MAC и инфо
                    if macaca:
                        print(f"MAC-таблица:\n{output_mac}")
                    else:
                        print("MAC-таблица: пуста")
                    print(f"Информация о порте:\n   {port_info_line}")
                    # Показываем, почему не сработало (опционально)
                    if not (is_access and has_vlan_YYYY and is_down):
                        print(f"Условия не выполнены")


        # === ОБРАБОТКА МОДЕЛИ 29 (SNR 29XX и аналоги) ===
        elif model == "29":
            print("\nВыполняем 'show int eth status'...")
            output_eth_status = connection.send_command("show int eth status", delay_factor=2)
            print(f"Вывод:\n{output_eth_status}\n")
            # Извлекаем порты в формате X/X или X/X/X
            ports_numeric = []
            for line in output_eth_status.splitlines():
                line = line.strip()
                if not line or any(header in line for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                    continue
                match = re.search(r'^(\d+/\d+(?:/\d+)?)', line)
                if match:
                    port = match.group(1)
                    if '/' in port:  # Убедимся, что это порт, а не скорость
                        ports_numeric.append(port)
            ports_numeric = list(dict.fromkeys(ports_numeric))  # Уникальные
            print(f"Извлеченные порты: {ports_numeric}\n")
            # Интерактивный выбор
            selected_ports = select_ports(ports_numeric, model)
            # Обработка каждого выбранного порта
            for port in selected_ports:
                full_port = f"Ethernet{port}"  # Cisco CLI требует "Ethernet1/0/1"
                print(f"\nОбработка порта: {port} {full_port}")
                # show mac-address-table int Ethernet<порт>
                print(f"show mac-address-table int {full_port}")
                try:
                    output_mac = connection.send_command(f"show int eth status | inc {port} | ex /1")
                    print(f"{output_mac}\n")
                except Exception as e:
                    print(f"Ошибка: {e}\n")
                # Проверка MAC-адресов
                print(f"show mac address-table interface {full_port}")
                try:
                    output_mac = connection.send_command(f"show mac-address-table interface {full_port}")
                    match = re.search(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}[\.\-]){2}[0-9A-Fa-f]{4}\b|\b[0-9A-Fa-f]{12}\b',output_mac)
                    if match:
                        macaca = match.group()
                        print(f"MAC-адрес найден: {macaca}")
                        print("\n" + "="*60)
                        print(f'"Проверьте сессию абонента PPPoE ses={macaca} или если DHCP-абонента mfses={macaca}"')
                        print("="*60)
                    else:
                        print("MAC-адрес не найден")
                        macaca = None
                except Exception as e:
                    print(f"Ошибка MAC: {e}")
                port_info_line = None
                for line in output_eth_status.splitlines():
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    if any(header in line_clean for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                        continue
                    # Точное совпадение по началу строки или пробелу после порта
                    if line_clean.startswith(port + " ") or f" {port} " in line_clean:
                        port_info_line = line_clean
                        break
                match_vl = re.search(r'\b(?:XXXX|3[1-9]\d{2})\b', port_info_line)
                if match_vl:
                    match_vlan = match_vl.group()
                    print(f"Номер vlan: {match_vlan}")
                else:
                    print("Номер vlan not XXXX and not 31xx")
                    match_vlan = None
                if not port_info_line:
                    print(f"Не найдена строка порта в show int eth status: {port}")
                    continue
                # Проверка условий: access, YYYY, down
                is_access = "auto" in port_info_line.lower()
                has_vlan_YYYY = "YYYY" in port_info_line
                is_down = "down" in port_info_line.lower()
                is_up = "up" in port_info_line.lower()
                is_access1 = "f-" in port_info_line.lower()
                is_access2 = "a-" in port_info_line.lower()
                is_trunk = "trunk" in port_info_line.lower()
                condition_met = False
                vlan_to_use = ""                
                # Условие для автоматического описания
                should_process = False
                flat_input = ""
                if (is_access or is_access1 or is_access2) and has_vlan_YYYY and (is_down or is_up) and macaca == None and is_trunk != "trunk":
                    print(f"Условия выполнены: auto={is_access}, f-={is_access1}, a-={is_access2}, vYYYY={has_vlan_YYYY}, down={is_down}, up={is_up}, trunk={is_trunk}, mac={macaca} 'Отключаем порт'")
                    output_sh_run_int_start = connection.send_command(f"show run int {full_port}")
                    print(output_sh_run_int_start)
                    condition_met = True
                    vlan_to_use = "ZZZZ"  # Для первого условия используем vlan ZZZZ
                elif match_vlan != None and (is_access or is_access1 or is_access2) and (is_down or is_up) and macaca == None and is_trunk != "trunk":
                    print(f"Условия выполнены: auto={is_access}, f-={is_access1}, a-={is_access2}, v={match_vlan}, down={is_down}, up={is_up}, trunk={is_trunk}, mac={macaca} 'Отключаем порт'")
                    output_sh_run_int_start = connection.send_command(f"show run int {full_port}")
                    print(output_sh_run_int_start)
                    condition_met = True
                    vlan_to_use = "1"  # Для elif условия используем vlan 1
                else:            
                    print(f"Условия не выполнены: access={is_access}, access1={is_access1}, access2={is_access2}, vYYYY={has_vlan_YYYY}, down={is_down}, up={is_up}, trunk={is_trunk}, mac={macaca}, v={match_vlan}")
                    if is_trunk == True:
                        print("PORT TRUNK")
                        break
                    if match_vlan == None:
                        vlan_to_use = "ZZZZ"
                    else: vlan_to_use = "1"
                    print(vlan_to_use)   
                    if macaca != None:
                        print("\nВнести изменения принудительно?")
                        user_input2 = input("Ваш выбор: ").strip()
                        print(user_input2)    
                        if user_input2.lower() == 'y':
                            # flat_input = "(f'kvkvartira')"
                            print(flat_input)
                            should_process = True
                            condition_met = True
                        else:
                            print("Завершена работа")
                            break
                    else:
                        print("Завершена работа")
                        break
                # Если условие выполнено (if или elif), продолжаем обработку
                if condition_met:
                    # Проверяем, определена ли flat_input1, если нет - запрашиваем
                    if not 'flat_input' in locals() or not flat_input:
                        flat_input = (f"kv{kvartira}")
                        print(flat_input)                
                    print("\nВнести изменения для данного порта?")
                    user_input2 = input("Ваш выбор: ").strip()
                    print(user_input2)         
                    if user_input2.lower() == 'y':
                        try:
                            # Проверка привилегированного режима
                            if not connection.check_enable_mode():
                                print("Вхожу в enable режим...")
                                connection.enable()
                            # Отправляем команды через send_command (без send_config_set)
                            config_commands = [
                                "conf t",
                                f"interface {full_port}",
                                f"description free_{flat_input}",
                                f"switch access vlan {vlan_to_use}",
                                f"shutdown",
                                f"exit",
                                f"exit",
                            ]    
                            output = ""
                            for cmd in config_commands:
                                print(f"{cmd}")
                                output += connection.send_command(cmd, expect_string=r'[>#]', delay_factor=2)
                            time.sleep(5)
                            output123 = connection.send_command_timing("write", delay_factor=2)
                            print("Ответ на write:")
                            print(output123)
                            # Проверяем, нужно ли подтверждение
                            if "Confirm to overwrite" in output123 or "[Y/N]" in output123:
                                time.sleep(1)    
                                # Отправляем "y" (строчная или заглавная - не важно)
                                confirm_output123 = connection.send_command_timing("y", delay_factor=2)                                
                                print("Отправлено подтверждение 'y'")
                                print("Результат:")
                                print(confirm_output123)
                            output_sh_run_int = connection.send_command(f"show run int {full_port}")
                            print(output_sh_run_int)
                            print(f"Успешно: interface {full_port}  Отключен")
                        except Exception as e:
                            print(f"Ошибка конфигурации: {e}")
                    else:
                        # Обычная обработка: показываем MAC и инфо
                        if macaca:
                            print(f"MAC-таблица:\n{output_mac}")
                        else:
                            print("MAC-таблица: пуста")
                        print(f"Информация о порте:\n   {port_info_line}")
                        # Показываем, почему не сработало (опционально)
                        if not (is_access and has_vlan_YYYY and is_down):
                            print(f"Условия не выполнены")

        elif model == "Cisco":
            print("\nВыполняем 'show int status'...")
            output_eth_status = connection.send_command("show int status", delay_factor=2)
            print(f"Вывод:\n{output_eth_status}\n")
            ports_numeric = []
            for line in output_eth_status.splitlines():
                line = line.strip()
                if not line or any(header in line for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                    continue
                match = re.search(r'^(Fa\d+/\d+|fa\d+/\d+)', line)
                if match:
                    port = match.group(1)
                    if '/' in port:  # Убедимся, что это порт, а не скорость
                        ports_numeric.append(port)
            ports_numeric = list(dict.fromkeys(ports_numeric))  # Уникальные
            print(f"Извлеченные порты: {ports_numeric}\n")
            # Интерактивный выбор
            selected_ports = select_ports(ports_numeric, model)
            # Обработка каждого выбранного порта
            for port in selected_ports:
                full_port = f"{port}"  # Cisco CLI требует "Ethernet1/0/1"
                print(f"\nОбработка порта: {port} {full_port}")
                # show mac-address-table int Ethernet<порт>
                print(f"   show mac-address-table int {full_port}")
                try:
                    output_mac = connection.send_command(f"show int status | inc {port} | ex /1")
                    print(f"{output_mac}\n")
                except Exception as e:
                    print(f"Ошибка: {e}\n")
                # Проверка MAC-адресов
                print(f"   show mac address-table interface {full_port}")
                try:
                    output_mac = connection.send_command(f"show mac-address-table interface {port}")
                    match = re.search(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}[\.\-]){2}[0-9A-Fa-f]{4}\b|\b[0-9A-Fa-f]{12}\b',output_mac)
                    if match:
                        macaca = match.group()
                        print(f"MAC-адрес найден: {macaca}")
                        print("\n" + "="*60)
                        print(f'"Проверьте сессию абонента PPPoE ses={macaca} или если DHCP-абонента mfses={macaca}"')
                        print("="*60)
                    else:
                        print("MAC-адрес не найден")
                        macaca = None
                except Exception as e:
                    print(f"Ошибка MAC: {e}")
                # Поиск строки порта в show int eth status
                port_info_line = None
                for line in output_eth_status.splitlines():
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    if any(header in line_clean for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                        continue
                    # Точное совпадение по началу строки или пробелу после порта
                    if line_clean.startswith(port + " ") or f" {port} " in line_clean:
                        port_info_line = line_clean
                        break
                if not port_info_line:
                    print(f"Не найдена строка порта в show int eth status: {port}")
                    continue
                is_access = "auto" in port_info_line.lower()
                has_vlan_YYYY = "YYYY" in port_info_line
                is_down = "disable" in port_info_line.lower()
                is_up = "connect" in port_info_line.lower()
                is_not = "notconnect" in port_info_line.lower()
                is_access1 = "a-" in port_info_line.lower()
                is_access2 = "f-" in port_info_line.lower()
                # Условие для автоматического описания
                should_process = False
                flat_input3 = ""
                if (is_access or is_access1 or is_access2) and has_vlan_YYYY and (is_down or is_up or is_not) and macaca == None:
                    print(f"Условия выполнены: auto={is_access}, a-={is_access1}, f-={is_access2}, vYYYY={has_vlan_YYYY}, down={is_down}, up={is_up}, notconnect ={is_not} Отключаем порт")
                    output_sh_run_int_start = connection.send_command(f"show run int {port}")
                    print(output_sh_run_int_start)
                    should_process = True
                else:            
                    print(f"Условия не выполнены: auto={is_access}, a-={is_access1}, f-={is_access2}, vYYYY={has_vlan_YYYY}, down={is_down}, up={is_up}, notconnect ={is_not}")
                    if macaca != None:                   
                        print("\nВнести изменения принудительно?")
                        user_input3 = input("Ваш выбор: ").strip()
                        print(user_input3)
                        if user_input3.lower() == 'y':
                            flat_input3 = (f"kv{kvartira}")
                            print(flat_input3)
                            should_process = True
                        else:
                            break    
                    else:
                        break
                if should_process:
                    if not flat_input3:
                        flat_input3 = (f'kv{kvartira}')
                        print(flat_input3)                                 
                print("\nВнести изменения для данного порта?")
                user_input1 = input("Ваш выбор: ").strip()
                print(user_input1)
                if user_input1.lower() == 'y':
                    try:
                        # Проверка привилегированного режима
                        if not connection.check_enable_mode():
                            print("Вхожу в enable режим...")
                            connection.enable()
                        # Отправляем команды через send_command (без send_config_set)
                        config_commands = [
                            "conf t",
                            f"interface {full_port}",
                            f"description free_{flat_input3}",
                            f"switch access vlan ZZZZ",
                            f"shutdown",
                            f"exit",
                            f"exit",
                            f"write memory"
                        ]          
                        output = ""
                        for cmd in config_commands:
                            print(f" {cmd}")
                            output += connection.send_command(cmd, expect_string=r'[>#]', delay_factor=2)
                        time.sleep(5)
                        output_sh_run_int = connection.send_command(f"show run int {full_port}")
                        print(output_sh_run_int)
                        print(f"Успешно: interface {full_port} Отключен")
                    except Exception as e:
                        print(f"Ошибка конфигурации: {e}")
                else:
                    # Обычная обработка: показываем MAC и инфо
                    if macaca:
                        print(f"MAC-таблица:\n{output_mac}")
                    else:
                        print("MAC-таблица: пуста")
                    print(f"Информация о порте:\n   {port_info_line}")
                    # Показываем, почему не сработало (опционально)
                    if not (is_access or is_access1 or is_access2) and has_vlan_YYYY and (is_down or is_up or is_not) and macaca == None:
                        print(f"Условия не выполнены")

        # === DLINK DES-32xx ===
        else:                  
                connection = ConnectHandler(**device_unknown)
                try:         
                    output_switch = connection.send_command_timing("show switch", delay_factor=2)
                    time.sleep(2)
                    print(f"Вывод show switch:\n{output_switch}\n")                       
                    command_accessrevC2011 = f'show ports desc'
                    output_accessrevC2011 = connection.send_command(command_accessrevC2011)
                    print(f"\nКоманда '{command_accessrevC2011}' выполнена. Вывод:")
                    print(output_accessrevC2011)
                    # Извлекаем порты в формате geX/X, xeX/X
                    ports_with_prefix1 = []
                    for line in output_accessrevC2011.splitlines():
                        line = line.strip()
                        if not line or any(header in line for header in ['Port', 'Name', 'Status', 'Vlan', 'Duplex', 'Speed', 'Type']):
                            continue
                        match = re.search(r'^(\d+)(?:\s+\([CF]\))?', line)
                        if match:
                            port = match.group(1)
                            ports_with_prefix1.append(port)
                    ports_with_prefix1 = list(dict.fromkeys(ports_with_prefix1))  # Уникальные, сохраняя порядок
                    print(f"Извлеченные порты: {ports_with_prefix1}\n")
                    # Интерактивный выбор портов
                    selected_ports1 = select_ports(ports_with_prefix1, model)
                    # Обработка каждого выбранного порта
                    for port in selected_ports1:
                        print(f"\nОбработка порта: {port}")
                        print(f"show vlan port {port}")
                        try:
                            output_mac_des = connection.send_command(f"show vlan port {port}")
                            print(f"{output_mac_des}\n")                            
                            match_vl = re.search(r'\b(?:XXXX|3[1-9]\d{2})\b', output_mac_des)
                            if match_vl:
                                match_vlan = match_vl.group()
                                print(f"Номер vlan: {match_vlan}")
                            else:
                                print("Номер vlan не найден")
                                match_vlan = None
                            if "XXXX" in output_mac_des and "X" in output_mac_des:                                            
                            # Проверяем условия для каждой строки с данными
                                result = "XXXX untagged"
                            else:            
                                result = (f"VLAN {match_vlan}")
                            print(result)
                        except Exception as e:
                            print(f"Ошибка MAC: {e}")
                        print(f"show fdb port {port}")
                        try:
                            output_mac = connection.send_command(f"show fdb port {port}")
                            print(f"{output_mac}\n")
                            match = re.search(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}[\.\-]){2}[0-9A-Fa-f]{4}\b|\b[0-9A-Fa-f]{12}\b', output_mac)
                            if match:
                                macaca = match.group()
                                print(f"MAC-адрес найден: {macaca}")
                                print("\n" + "="*60)
                                print(f'"Проверьте сессию абонента PPPoE ses={macaca} или если DHCP-абонента mfses={macaca}"')
                                print("="*60)                          
                            else:
                                print("MAC-адрес не найден")
                                macaca = None
                            if "XXXX" in output_mac and "comtel_pppoe" in output_mac:
                                result1 = "vlan XXXX"     
                            else:            
                                result1 = (f'{match_vlan}')
                            print(result1)
                        except Exception as e:
                            print(f" Ошибка: {e}")
                        print(f"show ports {port}")                        
                        output_mac1 = connection.send_command(f"show ports {port}")
                        print(f"{output_mac1}\n")
                        if "Down" in output_mac1:
                            result2 = "DOWN"   
                        else:            
                            result2 = "UP"
                        print(result2)
                        # Условие для автоматического описания (ПРОВЕРЯЕМ, ЧТО mac_address МОЖЕТ БЫТЬ None)
                        should_process = False
                        flat_input3 = ""
                        if (result2 == "DOWN" or result2 == "UP") and match_vlan != None and macaca == None:  # ← Теперь mac_address всегда инициализирована
                            print(f"Условия выполнены: vlan={match_vlan}, up/down={result2}, mac={macaca} Отключаем порт")
                            output_sh_run_int_start = connection.send_command(f"show vlan port {port}")
                            print(output_sh_run_int_start)
                            should_process = True
                        else:
                            print(f"Условия не выполнены: vlan={match_vlan}, vlanXXXX={result}, up/down={result2}, mac={macaca}")
                            if macaca != None:       
                                print("\nВнести изменения принудительно?")
                                user_input3 = input("Ваш выбор: ").strip()
                                print(user_input3)
                                if user_input3.lower() == 'y':
                                    flat_input3 = (f"kv{kvartira}")
                                    should_process = True
                                else:
                                    break    
                            else:
                                break
                        if should_process:
                            if not flat_input3:
                                flat_input3 = (f"kv{kvartira}")
                                print(flat_input3)              
                        print("\nВнести изменения для данного порта?")
                        user_input1 = input("Ваш выбор: ").strip()
                        print(user_input1)
                        if user_input1.lower() == 'y':
                            print(f"Условия выполнены:")
                            output_sh_run_int_start = connection.send_command(f"show vlan port {port}")
                            print(output_sh_run_int_start)
                            settings_ports = connection.send_command(f"config vlan vlanid {match_vlan} delete {port}", delay_factor=2)
                            print(settings_ports)
                            settings_ports1 = connection.send_command(f" config ports {port} desc free_{flat_input3}", delay_factor=2)
                            print(settings_ports1)
                            output_sh_run_int_start = connection.send_command(f"show vlan port {port}")
                            print(output_sh_run_int_start)
                            settings_ports = connection.send_command(f"save",  delay_factor=2)
                            print(settings_ports)
                            print(output_sh_run_int_start)
                        else:
                            print(f"Условия не выполнены:")
                except Exception as e:
                    print(f"Ошибка выполнени: {e}")
    except Exception as e:
        print(f"\nОшибка подключения или выполнения: {e}")
        print("Проверьте:")
        print("IP-адрес, логин, пароль")
        print("доступность устройства")
        print("поддержку SSH/Telnet")
        print("права на enable")

# --- ЗАПУСК ---
if __name__ == "__main__":
    main()

