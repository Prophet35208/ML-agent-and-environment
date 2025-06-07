# Сохраняем текущую директорию
$OriginalDir = Get-Location

# Переходим в папку .venv\Scripts
cd .venv\Scripts

# Проверяем, существует ли файл Activate.ps1
if (Test-Path Activate.ps1) {
    # Активируем виртуальное окружение
    . .\Activate.ps1

    # Проверяем, успешно ли активировано окружение
    if ($env:VIRTUAL_ENV) {
        Write-Host "Виртуальное окружение активировано."

        # Возвращаемся в исходную папку
        cd $OriginalDir

        # Проверяем, удалось ли вернуться в исходную папку
        if ($?) {
            Write-Host "Перешли в исходную директорию: $($OriginalDir)"

            # Запускаем agentSimpleRoad.py
            python envSimpleRoad.py

            # Проверяем, успешно ли запустился скрипт
            if ($?) {
            } else {
                Write-Host "Ошибка при запуске скрипта agentSimpleRoad.py"
            }
        } else {
            Write-Host "Ошибка при переходе в исходную директорию."
        }

    } else {
        Write-Host "Ошибка: Не удалось активировать виртуальное окружение."
    }
} else {
    Write-Host "Ошибка: Файл Activate.ps1 не найден в папке .venv\Scripts. Проверьте путь к вашему виртуальному окружению."
}

# Приостанавливаем выполнение, чтобы можно было увидеть результаты
Read-Host "Нажмите Enter для выхода"