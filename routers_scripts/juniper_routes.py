import ipaddress
import requests

def is_subnet_occupied(network, occupied_ips):
    for ip in network:
        if str(ip) in occupied_ips:
            return True
    return False

def get_occupied_ips(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return set(line.strip() for line in response.text.splitlines() if line.strip())
    except Exception as e:
        print(f"Ошибка при загрузке файла с занятыми IP: {e}")
        print("Продолжаем без проверки занятости IP.")
        return set()

def get_occupied_ips_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"Ошибка при чтении файла с занятыми IP: {e}")
        print("Продолжаем без проверки занятости IP из файла.")
        return set()

def generate_juniper_command():
    occupied_billing = set()
    occupied_billing.update(get_occupied_ips("http://x.x.x.x:55555/blockied_ip_1.txt"))
    occupied_billing.update(get_occupied_ips("http://y.y.y.y:55555/blocked_ip.txt"))

    file_path = r"D:\Путь\к\файлу\RIPJUN.txt"
    file_path1 = r"D:\Путь\к\файлу\zapret.txt"

    occupied_juniper = get_occupied_ips_from_file(file_path)
    occupied_juniper1 = get_occupied_ips_from_file(file_path1)
    try:
        unit = input("Введите номер юнита (например, 401): ").strip()
        if not unit.isdigit():
            raise ValueError("Номер юнита должен быть числом")

        while True:
            subnet = input("Введите номер подсети с маской (например, X.X.X.X/30): ").strip()
            try:
                network = ipaddress.IPv4Network(subnet, strict=False)
            except ValueError as e:
                print(f"Ошибка: {e}. Введите корректную подсеть.")
                continue

            occupied_in_billing = is_subnet_occupied(network, occupied_billing)
            occupied_in_juniper = is_subnet_occupied(network, occupied_juniper)
            occupied_in_juniper1 = is_subnet_occupied(network, occupied_juniper1)

            if occupied_in_billing and occupied_in_juniper:
                print("IP ADDRESS ЗАНЯТ. Введите свободную подсеть.")
                continue
            elif occupied_in_juniper:
                print("Занят по джунипер. Введите свободную подсеть.")
                continue
            elif occupied_in_juniper1:
                print("Занят блок. Введите свободную подсеть.")
                continue
            elif occupied_in_billing:
                print("занят по биллингу. Введите свободную подсеть.")
                continue
            else:
                break

        policer = input("Введите полосу в (Mbps): ").strip()
        try:
            policer_mbps = int(policer)
            policer_kbps = policer_mbps * 1024
        except ValueError:
            print("Ошибка: Полоса должна быть числом (например, 10 или 10.5).")
            return

        first_ip = network.network_address + 1
        first_ip1 = network.network_address + 2
        subnet_mask = str(network.netmask)

        command5 = f"show route {network.network_address}/{network.prefixlen}"
        command7 = f'show configuration firewall family inet filter "Name_filter" term {network.network_address}/{network.prefixlen}'
        command6 = f'show configuration firewall family inet filter "Name_filter" term {first_ip1}/{network.prefixlen+2}'
        command8 = f'\n'
        command = f"set interfaces xe-0/0/1 unit {unit} family inet address {first_ip}/{network.prefixlen}"
        command1 = f'set firewall family inet filter "Name_filter" term {network.network_address}/{network.prefixlen} from address {network.network_address}/{network.prefixlen}'       
        command2 = f'set firewall family inet filter "Name_filter" term {network.network_address}/{network.prefixlen} then policer "{policer} Mbps"'
        command3 = f'insert firewall family inet filter "Name_filter" term {network.network_address}/{network.prefixlen} before term "Allow ALL"'

        print("\nСгенерированная команда:\n")
        print(command5)
        print(command7)
        print(command6)
        print(command8)
        print(command)
        print(command1)
        print(command2)
        print(command3)

        print(f"\n========================\n"
              f"Сеть для биллинга: {network.network_address}/{network.prefixlen}\n"
              f"========================\n\n"
              f"IP адрес: {first_ip1}\n"
              f"Маска подсети: {subnet_mask}\n"
              f"Шлюз: {first_ip}\n\n"
              f"DNS 1: z.z.z.z\n"
              f"DNS 2: w.w.w.w\n\n"
              f"==========================\n"
              f"p{policer_kbps}-полоса прописана\n")

    except ValueError as e:
        print(f"\nОшибка: {e}")
    except KeyboardInterrupt:
        print("\nОперация отменена пользователем")
        raise

if __name__ == "__main__":
    print("Введите данные (для выхода нажмите Ctrl+C)\n")
    while True:
        try:
            generate_juniper_command()
            print("Готово! Для нового ввода введите данные...\n")
        except KeyboardInterrupt:
            print("\nПрограмма завершена.")
            break

