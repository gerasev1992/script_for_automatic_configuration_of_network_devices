import netmiko
from collections import defaultdict
import time
import re  # Импорт regexp для улучшенного парсинга портов

# Список IP-адресов устройств для последовательного подключения
devices_ips = [
                "X.X.X.X",        
                ]  # Добавьте сюда другие IP-адреса по мере необходимости

# Проходим по всем устройствам из списка
for device_ip in devices_ips:
    print(f"\n{'='*60}")
    print(f"Начинаем работу с устройством {device_ip}")
    print(f"{'='*60}")
    
# Укажите параметры подключения
    device = {
        'device_type': 'dlink_ds',  # Используем поддержку D-Link DES series в netmiko; если не подходит, попробуйте 'generic'
        'ip': device_ip,        # Замените на IP-адрес вашего устройства
        'username': 'XXXXXX',        # Замените на ваше имя пользователя
        'password': 'YYYYYY',     # Замените на ваш пароль
        #'secret': 'enable_secret'  # Замените на enable-пароль, если требуется enable
    }

    try:
        # Подключаемся к устройству
        connection = netmiko.ConnectHandler(**device)
        print("Подключение установлено.")

        # Отправляем команду show traffic_segmentation
        output = connection.send_command('show traffic_segmentation')
        print("Команда 'show traffic_segmentation' выполнена. Вывод:")
        print(output)

        # Парсим вывод: предполагаем tab-separated таблицу с заголовком в первой строке
        lines = output.strip().split('\n')
        if len(lines) > 1:  # Есть данные после заголовка
            port_numbers = []
            for line in lines[9:]:  # Пропускаем заголовок
                columns = line.split()  # Разделяем по пробелам
                if columns:  # Если есть столбцы
                    port_numbers.append(columns[0])  # Первый столбец - номер порта
            print(f"Номера портов из traffic_segmentation: {','.join(port_numbers)}")
        else:
            print("Нет данных для парсинга в 'show traffic_segmentation'.")

        # Отправляем команду show vlan
        output_vlan = connection.send_command('show vlan')
        print("\nКоманда 'show vlan' выполнена. Вывод:")
        print(output_vlan)

        # Парсим вывод: ищем четырехзначные VLAN ID, начинающиеся на 4
        lines_vlan = output_vlan.strip().split('\n')
        vlan_ids = []
        for line in lines_vlan[1:]:  # Пропускаем заголовок, если есть
            columns = line.split()  # Разделяем по пробелам
            if len(columns) > 0:
                # Предполагаем, что VLAN ID в первом столбце; если нет, настройте индекс
                possible_vlan = columns[2]
                if len(possible_vlan) == 4 and possible_vlan.startswith('4') and possible_vlan.isdigit():
                    vlan_ids.append(possible_vlan)
        
        # Записываем найденные VLAN ID в переменную vlan_mgmt
        vlan_mgmt = vlan_ids
        print("Найденные четырехзначные VLAN ID, начинающиеся на 4:")
        print(vlan_mgmt)

        # Если vlan_mgmt не пуст, отправляем команду show conf cur inc для каждого VLAN
        tag_ports = []  # Переменная для хранения портов после "tagged"
        if vlan_mgmt:
            for vlan_id in vlan_mgmt:
                command = f'show config current include "config vlan {vlan_id} add tag"'
                output_conf = connection.send_command(command)
                print(f"\nКоманда '{command}' выполнена для VLAN {vlan_id}. Вывод:")
                print(output_conf)
                
                # Изменённый парсинг: используем регулярные выражения для извлечения портов/диапазонов после "add tagged"
                lines_conf = output_conf.strip().split('\n')
                for line in lines_conf:
                    if 'add tagged' in line.lower():
                        parts = line.lower().split('add tagged')
                        if len(parts) > 1:
                            ports_str = parts[1].strip()
                            # Используем regexp для поиска одиночных портов (\d+) и диапазонов (\d+-\d+)
                            found_ports = re.findall(r'\b(\d+(?:-\d+)?)\b', ports_str)
                            for port_range in found_ports:
                                if '-' in port_range:
                                    # Обработка диапазона, например "25-28" -> 25,26,27,28
                                    try:
                                        start, end = map(int, port_range.split('-'))
                                        port_list = [str(i) for i in range(start, end + 1)]
                                        tag_ports.extend(port_list)
                                    except ValueError:
                                        pass  # Пропустить, если диапазон некорректен
                                else:
                                    # Одиночный порт
                                    tag_ports.append(port_range)
            print(f"\nСобранные tag_ports (downlink-порты): {','.join(tag_ports)}")
        else:
            print("\nНет подходящих VLAN ID для выполнения команды.")

        # Создаем переменную access_ports: порты из traffic_segmentation за вычетом tag_ports (без повторений)
        if port_numbers and tag_ports:
            access_ports = [port for port in port_numbers if port not in tag_ports]
            print(f"\naccess_ports (порты из traffic_segmentation, исключая tag_ports): {','.join(access_ports)}")
        else:
            access_ports = port_numbers if port_numbers else []
            print(f"\naccess_ports (нет tag_ports для исключения): {','.join(access_ports)}")

        # Дополнительно: для каждого VLAN в vlan_mgmt выполняем "show fdb vlan {vlan_id}" и определяем UPLINK как наиболее встречаемый номер порта в столбце Port (игнорируя CPU и прочие не-дигитовые значения; при равенстве частот выбираем наименьший порт)
        uplink_ports = {}  # Словарь для хранения: ключ - vlan_id, значение - {'uplink_port': str, 'max_count': int, 'all_ports': list}
        if vlan_mgmt:
            for vlan_id in vlan_mgmt:
                command_fdb = f'show fdb vlan {vlan_id}'
                output_fdb = connection.send_command(command_fdb)
                print(f"\nКоманда '{command_fdb}' выполнена для VLAN {vlan_id}. Вывод:")
                print(output_fdb)
                
                # Парсим вывод: таблица (VID VLAN Name MAC Port Type); используем split() для строк данных (предполагаем, что Name без пробелов, как в примере)
                lines_fdb = output_fdb.strip().split('\n')
                port_counts = defaultdict(int)  # Счётчик частот портов
                all_ports = []
                if len(lines_fdb) > 1:  # Есть данные после заголовка
                    for line in lines_fdb[1:]:
                        columns_fdb = line.split()
                        if len(columns_fdb) >= 4:  # Ожидаем минимум 4 столбца (VID, Name, MAC, Port, Тип)
                            try:
                                port = columns_fdb[3]  # Столбец Port
                                if port.isdigit():  # Игнорируем CPU и другие не-дигитовые
                                    port_counts[port] += 1
                                    all_ports.append(port)
                            except IndexError:
                                pass  # Пропустить строку, если формат не совпадает
                
                # Определяем UPLINK: порт с максимальным количеством вхождений
                uplink_port = None
                max_count = 0
                for port in sorted(port_counts.keys(), key=int):  # Сортировка по портам как числа (чтобы при равенстве взять меньший)
                    if port_counts[port] > max_count:
                        max_count = port_counts[port]
                        uplink_port = port
                
                # Сохраняем результат
                if uplink_port:
                    uplink_ports[vlan_id] = {
                        'uplink_port': uplink_port,
                        'max_count': max_count,
                        'all_ports': all_ports
                    }
                    print(f"Для VLAN {vlan_id} определён UPLINK-порт: {uplink_port} (частота: {max_count})")
                else:
                    uplink_ports[vlan_id] = {
                        'uplink_port': 'Не определён',
                        'max_count': 0,
                        'all_ports': all_ports
                    }
                    print(f"Для VLAN {vlan_id} UPLINK-порт не определён (нет цифровых портов в FDB).")
            
            print(f"\nИтоговые UPLINK-порты: {uplink_ports}")
        else:
            print("\nНет VLAN ID для анализа FDB.")

        # Новый шаг: вводим команду "show config current include "create access_profile""
        command_access = 'show config current include "create access_profile"'
        output_access = connection.send_command(command_access)
        print(f"\nКоманда '{command_access}' выполнена. Вывод:")
        print(output_access)

        # Проверяем вывод: если в какой-либо строке содержится "vlan 0xFFF", то выбрать "access_profile_vlan 0xFFF"
        # Иначе выбрать "access_profile_vlan"
        selected_access_profile = "create access_profile  ethernet  vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type  profile_id 20"  # По умолчанию
        if "create access_profile  ethernet  vlan 0xFFF source_mac" in output_access:
            selected_access_profile = f'create access_profile  ethernet  vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type  profile_id 20'
        elif "create access_profile profile_id" in output_access:
            selected_access_profile = "create access_profile profile_id 20 ethernet vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type"
        elif "create access_profile  ethernet  vlan source_mac" in output_access:
            selected_access_profile = "create access_profile  ethernet  vlan source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type  profile_id 20"                  
        elif "No filter matched result!" in output_access:
            selected_access_profile = "create access_profile  ethernet  vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type  profile_id 20"
        elif "No filter matched." in output_access:
            selected_access_profile = "create access_profile profile_id 20 ethernet vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type"                              
        print(f"\nВыбранный access_profile: {selected_access_profile}")

        command_addvlan1530 = 'create vlan xxxx tag 1530'
        output_addvlan1530 = connection.send_command(command_addvlan1530)
        print(f"\nКоманда '{command_addvlan1530}' выполнена. Вывод:")

        command_addvlan1531 = 'create vlan yyyy tag 1531'
        output_addvlan1531 = connection.send_command(command_addvlan1531)
        print(f"\nКоманда '{command_addvlan1531}' выполнена. Вывод:")

        command_acl = 'delete access_profile all'
        output_acl = connection.send_command(command_acl)
        print(f"\nКоманда '{command_acl}' выполнена. Вывод:")

        try:
            result = connection.send_command(selected_access_profile)
            print(f"Команда '{selected_access_profile}' отправлена. Результат:")
            print(result)
        except Exception as e:
            print(f"Ошибка при отправке команды: {e}")

            command_access = 'show config current include "create access_profile"'
            output_access = connection.send_command(command_access)
            print(f"\nКоманда '{command_access}' выполнена. Вывод:")
            print(output_access)

        if "create access_profile  ethernet  vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type  profile_id 20" in output_access:
            print("\nОбнаружен profile_id 20. Загружаем дополнительные команды...")

            command_access1 = f'config access_profile profile_id 20  add access_id 1  ethernet  vlan xxxx source_mac 00-12-00-00-00-00 mask FF-FF-FF-FF-FF-00 destination_mac 00-00-00-00-00-00 mask 00-00-00-00-00-00  port  {','.join(access_ports)} deny'
            output_access1 = connection.send_command_timing(command_access1)
            time.sleep(2)
            print(f"\nКоманда '{command_access1}' выполнена. Вывод:")
            print(output_access1)
        
            command_access2 = f'config access_profile profile_id 20  add access_id 2  ethernet  vlan yyyy source_mac 00-12-00-00-00-00 mask FF-FF-FF-FF-FF-00 destination_mac 00-00-00-00-00-00 mask 00-00-00-00-00-00  port  {','.join(access_ports)} deny'
            output_access2 = connection.send_command_timing(command_access2)
            time.sleep(2)
            print(f"\nКоманда '{command_access2}' выполнена. Вывод:")
            print(output_access2)
        
            command_access3 = f'config access_profile profile_id 20  add access_id 3  ethernet  vlan xxxx source_mac 00-00-00-00-00-00 mask 00-00-00-00-00-00 destination_mac FF-FF-FF-FF-FF-FF ethernet_type 0x8863    port {','.join(access_ports)} permit'
            output_access3 = connection.send_command_timing(command_access3)
            time.sleep(2)
            print(f"\nКоманда '{command_access3}' выполнена. Вывод:")
            print(output_access3)
        
            .............................

        else:
           
            #rev.C
            command_accessrevC201 = f'create access_profile profile_id 20 ethernet vlan 0xFFF source_mac FF-FF-FF-FF-FF-00 destination_mac FF-FF-FF-FF-FF-00 ethernet_type'
            output_accessrevC201 = connection.send_command_timing(command_accessrevC201)
            time.sleep(2)
            print(f"\nКоманда '{command_accessrevC201}' выполнена. Вывод:")
            print(command_accessrevC201)

            command_accessrevC202 = f'config access_profile profile_id 20  add access_id 1  ethernet vlan_id 1530 source_mac 00-12-00-00-00-00 mask FF-FF-FF-FF-FF-00 destination_mac 00-00-00-00-00-00 mask 00-00-00-00-00-00 port {','.join(access_ports)} deny'
            output_accessrevC202 = connection.send_command_timing(command_accessrevC202)
            time.sleep(2)
            print(f"\nКоманда '{command_accessrevC202}' выполнена. Вывод:")
            print(output_accessrevC202)

            command_accessrevC203 = f'config access_profile profile_id 20  add access_id 2  ethernet vlan_id 1531 source_mac 00-12-00-00-00-00 mask FF-FF-FF-FF-FF-00 destination_mac 00-00-00-00-00-00 mask 00-00-00-00-00-00 port {','.join(access_ports)} deny'
            output_accessrevC203 = connection.send_command_timing(command_accessrevC203)
            time.sleep(2)
            print(f"\nКоманда '{command_accessrevC203}' выполнена. Вывод:")
            print(output_accessrevC203)

        command_save = 'save'
        output_save = connection.send_command(command_save)
        print(f"\nКоманда '{command_save}' выполнена. Вывод:")


    except Exception as e:
            print(f"Ошибка при отправке команды: {e}")

        # Закрываем подключение
    connection.disconnect()
    print("Подключение закрыто.")
