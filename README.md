# igi plugins for Metashape
Плагины Agisoft Metashape для использования при создании топографических планов.

## Установка
### 1. Установка библиотеки _pyautocad_ для python интерпретатора, встроенного в Agisoft Metashape
#### Вариант 1
Установка через команду `pip install pyautocad` в консоли Metashape. или в интерпретаторе python от Metashape.
Интерпретатор python от Metashape при стандартной установке программы лежит в 
`C:\Program Files\Agisoft\Metashape Pro\python`.
#### Вариант 2
Установка через интерпретатор python. Интерпретатор от Metashape при стандартной установке программы лежит в `C:\Program Files\Agisoft\Metashape Pro\python`. Вызвать командную строку из директории с интерпретатором и выполнить команду python `-m pip install pyautocad`.
### 2. Установка плагинов в Agisoft Metashape
Скачать исходный код из репозитория и разместить в папке `%localappdata%\Agisoft\Metashape Pro\scripts`

## Список плагинов
### Взаимодействие с Autocad
1. [Перенос фигур в Autocad](https://github.com/maxmyslivets/igi-plugins-for-Metashape/blob/dev/src/shape_transfer/README.md)
