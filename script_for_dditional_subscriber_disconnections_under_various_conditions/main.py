import os
import subprocess
import sys
import time

# Путь к каталогу со скриптами
SCRIPT_DIR = r"D:\..........."

def run_script(script_name):
    """Запускает скрипт по указанному пути"""
    script_path = os.path.join(SCRIPT_DIR, script_name)     
    # Проверяем существует ли файл
    if not os.path.exists(script_path):
        return 1
    try:
        # Запускаем скрипт
        result = subprocess.run(
            [sys.executable, script_path],
            cwd = SCRIPT_DIR,  # Устанавливаем рабочую директорию
            text = True
        )
        return result.returncode     
    except Exception as e:
        return 1

def run_all_scripts():   
    # Запускаем скрипты последовательно
    scripts = ["script_parsing_crm_TO_GIT.py", "shutdown_pppoe_port_TO_GIT.py"]   
    results = {}
    for script in scripts:
        results[script] = run_script(script)
    # Итог
    all_success = True
    for script, code in results.items():
        status = "УСПЕХ" if code == 0 else "ОШИБКА"
        if code != 0:
            all_success = False
    # print("\n" + "=" * 60)
    if all_success:
        print("ВСЕ СКРИПТЫ ВЫПОЛНЕНЫ УСПЕШНО!")
    else:
        print("НЕКОТОРЫЕ СКРИПТЫ ЗАВЕРШИЛИСЬ С ОШИБКАМИ")
        print("-" * 60)
    return all_success

def main():
    # Настройки
    DELAY_BETWEEN_RUNS = 2  # Задержка между запусками в секундах
    run_count = 0
    # Бесконечный цикл с автоматическим перезапуском
    while True:
        run_count += 1  
        # Запускаем все скрипты
        success = run_all_scripts()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("=" * 60)
