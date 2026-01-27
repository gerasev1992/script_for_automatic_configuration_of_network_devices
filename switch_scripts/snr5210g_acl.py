from netmiko import ConnectHandler
import getpass
import re
import time
from datetime import datetime

DEVICE_IPS = [	      
    #'X.X.X.X',	     
    #'Y.Y.Y.Y',	    
]

def parse_interfaces_with_acl(output):
    interfaces_acl = {}
    lines = output.strip().split('\n')
    
    current_interface = None
    for line in lines:
        line = line.strip()
        
        if line.startswith('interface '):
            match = re.search(r'interface\s+(ge\d+|xe\d+|Gi\d+|Te\d+|Fa\d+)', line)
            if match:
                current_interface = match.group(1)
                interfaces_acl[current_interface] = []
        elif current_interface:
            if 'mac access-group 100 in' in line:
                interfaces_acl[current_interface].append('mac access-group 100 in')
            elif 'mac access-group 150 in' in line:
                interfaces_acl[current_interface].append('mac access-group 150 in')
            elif 'mac access-group 160 in' in line:
                interfaces_acl[current_interface].append('mac access-group 160 in')    
    return {iface: acls for iface, acls in interfaces_acl.items() if acls}

def configure_device(device_ip, username, password, enable_password):

    print(f"\n{'='*60}")
    print(f"НАСТРОЙКА УСТРОЙСТВА: {device_ip}")
    print(f"Время начала: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        # Параметры устройства
        device = {
            'device_type': 'cisco_ios',
            'host': device_ip,
            'username': username,
            'password': password,
            'secret': enable_password,
            'timeout': 30,
        }
        
        connection = ConnectHandler(**device)
        connection.enable()
        
        output = connection.send_command("sh running-config interface | include mac|ge|xe")
        
        print(output)
        
        print("\n Анализ ACL на интерфейсах...")
        interfaces_with_acl = parse_interfaces_with_acl(output)
        
        if interfaces_with_acl:
            print(f"Найдено интерфейсов с ACL: {len(interfaces_with_acl)}")
            for interface, acls in interfaces_with_acl.items():
                print(f"  {interface}: {', '.join(acls)}")
        else:
            print("Интерфейсов с ACL не найдено")
            interfaces_with_acl = {}
        
        print("\n Удаление старых ACL...")
        connection.config_mode()
        
        remove_commands = [
            'no access-list 100',
            'no access-list 150',
            'no access-list 160',
        ]
        
        for cmd in remove_commands:
            print(f"  Выполняю: {cmd}")
            output = connection.send_command(cmd)
        
        print("\n Создание новых ACL...")
        new_acls = [
            'access-list 100 10 deny mac 0012.0000.0000 0000.0000.00FF any vlan 1530',
            'access-list 100 20 deny mac 00012.0000.0000 0000.0000.00FF any vlan 1531',
            'access-list 150 10 permit mac 00012.0000.0000 0000.0000.00FF any 0x8863 vlan 1530',
            'access-list 150 20 permit mac 00012.0000.0000 0000.0000.00FF any 0x8864 vlan 1531',
            'access-list 160 30 deny mac any any vlan 1510',
            'vlan 1531',
        ]
        
        for cmd in new_acls:
            print(f"  Выполняю: {cmd}")
            connection.send_command(cmd)
        
        if interfaces_with_acl:
            print("\n Восстановление ACL на интерфейсах...")
            
            for interface, acls in interfaces_with_acl.items():
                print(f"\n  Настройка интерфейса {interface}:")
                
                connection.send_command_timing(f"interface {interface}")
                
                for acl in acls:
                    print(f"    Применяю: {acl}")
                    output = connection.send_command_timing(acl)
                
                connection.send_command_timing("exit")
                
        else:
            print("\n Нет интерфейсов для применения ACL")
        
        connection.send_command_timing("end")
        connection.exit_config_mode()
        
        print("\n Сохранение и проверка конфигурации...")
        
        print("  Сохраняю конфигурацию...")
        output = connection.send_command("write")
               
        print("\n  Проверяю итоговую конфигурацию...")
        final_output = connection.send_command("show running-config interface | include mac|ge|xe")
        final_output1 = connection.send_command("show mac access-lists")
        
        
        print("\n  Итоговая конфигурация интерфейсов:")
        print("  " + "-" * 48)
        print("  " + "\n  ".join(final_output.split('\n')))
        print("  " + "-" * 48)
        print("  " + "\n  ".join(final_output1.split('\n')))
        print("  " + "-" * 48)             

        connection.disconnect()
        
        print(f"\n{'='*60}")
        print(f"УСТРОЙСТВО {device_ip} УСПЕШНО НАСТРОЕНО!")
        print(f"Время завершения: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"\n{'!'*60}")
        print(f"ОШИБКА на устройстве {device_ip}: {str(e)}")
        print(f"{'!'*60}")
        return False

def main():

    print("=" * 70)
    print("СКРИПТ ДЛЯ ПОСЛЕДОВАТЕЛЬНОЙ НАСТРОЙКИ ACL НА КОММУТАТОРАХ")
    print("=" * 70)
    
    if not DEVICE_IPS:
        print("\n⚠ ОШИБКА: Список DEVICE_IPS пуст!")
        print("Добавьте IP-адреса в список DEVICE_IPS в начале скрипта.")
        return
    
    print(f"\nВ списке найдено {len(DEVICE_IPS)} устройств для настройки:")
    for i, ip in enumerate(DEVICE_IPS, 1):
        print(f"  {i:2d}. {ip}")
    
    print("\n" + "-" * 70)
    print("ВВЕДИТЕ УЧЕТНЫЕ ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ")
    print("-" * 70)
    
    username = input("Имя пользователя: ")
    password = getpass.getpass("Пароль: ")
    enable_password = getpass.getpass("Пароль для enable режима (Enter если совпадает): ") or password
    
    print("\n" + "-" * 70)
    print(f"БУДЕТ НАСТРОЕНО УСТРОЙСТВ: {len(DEVICE_IPS)}")
    print("-" * 70)
    
    confirm = input(f"Начать последовательную настройку всех {len(DEVICE_IPS)} устройств? (y/n): ").lower()
    if confirm != 'y':
        print("Операция отменена.")
        return
      
    print(f"\n{'#' * 70}")
    print(f"НАЧАЛО ПОСЛЕДОВАТЕЛЬНОЙ НАСТРОЙКИ")
    print(f"Всего устройств в очереди: {len(DEVICE_IPS)}")
    print(f"Общее время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 70}")
    
    results = []
    successful_count = 0
    
    for i, device_ip in enumerate(DEVICE_IPS, 1):
        print(f"\n\n{'='*70}")
        print(f"УСТРОЙСТВО {i} ИЗ {len(DEVICE_IPS)}: {device_ip}")
        print(f"Прогресс: {i}/{len(DEVICE_IPS)} ({i/len(DEVICE_IPS)*100:.1f}%)")
        print(f"{'='*70}")
        
        success = configure_device(device_ip, username, password, enable_password)
        results.append({'ip': device_ip, 'success': success})
        
        if success:
            successful_count += 1
        
        if i < len(DEVICE_IPS):
            pause_time = 2
            print(f"\n{'~'*40}")
            print(f"Пауза {pause_time} сек. перед следующим устройством...")
            print(f"{'~'*40}")
            time.sleep(pause_time)
    
    print(f"\n\n{'#' * 70}")
    print("ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'#' * 70}")
    
    print(f"\nВсего обработано устройств: {len(results)}")
    print(f"Успешно настроено: {successful_count}")
    print(f"С ошибками: {len(results) - successful_count}")
    
    if len(results) - successful_count > 0:
        print(f"\n{'!'*70}")
        print("УСТРОЙСТВА С ОШИБКАМИ:")
        print(f"{'!'*70}")
        for result in results:
            if not result['success']:
                print(f" {result['ip']}")
    
    # Сохраняем краткий отчет в файл (если необходимо)
    #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #report_filename = f"acl_batch_report_{timestamp}.txt"
    
    #with open(report_filename, 'w', encoding='utf-8') as f:
    #    f.write(f"Отчет по последовательной настройке ACL\n")
    #    f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    #    f.write(f"Всего устройств: {len(results)}\n")
    #    f.write(f"Успешно: {successful_count}\n")
    #    f.write(f"С ошибками: {len(results) - successful_count}\n\n")
        
    #    f.write("Список устройств:\n")
    #    for i, ip in enumerate(DEVICE_IPS, 1):
    #        f.write(f"  {i}. {ip}\n")
        
    #    f.write(f"\nДетали:\n")
    #    for result in results:
    #        status = "УСПЕШНО" if result['success'] else "ОШИБКА"
    #        f.write(f"  {result['ip']}: {status}\n")

if __name__ == "__main__":
    main()



    
