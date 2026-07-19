import math
import tkinter as tk
from tkinter import messagebox, ttk

import Metashape as ms

from pyautocad.api import Autocad
from pyautocad import APoint

from shapely.geometry import Point, Polygon


def get_dem_height(dem, x, y):
    try:
        return dem.altitude(ms.Vector([x, y]))
    except Exception as e:
        print(e)
        return None


def get_point():

    print("Получение высоты из ЦММ в Autocad")

    chunk = ms.app.document.chunk
    acad = Autocad()

    if not chunk:
        raise Exception("Нет активного Chunk")

    if not chunk.elevation:
        raise Exception("DEM отсутствует")

    dem = chunk.elevation
    while True:
        try:
            pnt = acad.doc.Utility.GetPoint()

            x = pnt[0]
            y = pnt[1]
            print("x, y =", x, y)

            z = get_dem_height(dem, x, y)
            print("z =", z)

            if z is None:
                ms.app.messageBox("Точка находится вне границ ЦММ")
                return

            acad.model.AddText(f"{z:.2f}", APoint(x, y, z), 0.5)

            print(f"Создана отметка {z:.2f}")
        except Exception as e:
            print(e)
            break


def get_grid():
    print("Получение высоты из ЦММ в Autocad")

    chunk = ms.app.document.chunk
    acad = Autocad()

    if not chunk:
        raise Exception("Нет активного Chunk")

    if not chunk.elevation:
        raise Exception("DEM отсутствует")

    dem = chunk.elevation

    params = {}

    root = tk.Tk()
    root.title("Параметры сетки")
    root.geometry("400x200")
    root.resizable(False, False)

    # Переменные для хранения ввода
    step_var = tk.DoubleVar(value=10.0)
    align_to_line_var = tk.BooleanVar(value=False)

    # Элементы интерфейса
    frame = ttk.Frame(root, padding=15)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Расстояние между точками сетки (м):").grid(
        row=0, column=0, sticky="w", pady=5
    )
    ttk.Entry(frame, textvariable=step_var, width=15).grid(
        row=0, column=1, sticky="w", pady=5
    )

    ttk.Checkbutton(
        frame,
        text="Учесть направление (выбрать полилинию)",
        variable=align_to_line_var,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=15)

    def on_submit():
        if step_var.get() == 2:
            # Вычисляем угол наклона первого сегмента полилинии
            dx = line_coords[1][0] - line_coords[0][0]
            dy = line_coords[1][1] - line_coords[0][1]
            angle = math.atan2(dy, dx)
            print(f"Угол направления сетки: {math.degrees(angle):.2f}°")
        else:
            print(
                "Линия направления не выбрана. Используется стандартная сетка."
            )

    # Косинус и синус для поворота матрицы сетки
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    # Увеличиваем радиус поиска, чтобы покрыть повернутый прямоугольник bounds
    diag = math.hypot(max_x - min_x, max_y - min_y)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # Генерация точек в локальной системе координат сетки
    max_steps = int(diag / step) + 2

    points_created = 0

    for i in range(-max_steps, max_steps):
        for j in range(-max_steps, max_steps):
            # Локальные смещения относительно центра
            u = i * step
            v = j * step

            # Поворот и перенос в глобальные координаты AutoCAD
            x = center_x + u * cos_a - v * sin_a
            y = center_y + u * sin_a + v * cos_a

            # Проверка: попадает ли точка внутрь полигона
            pnt_geo = Point(x, y)
            if polygon.contains(pnt_geo):
                # Получение высоты из ЦММ Metashape
                z = get_dem_height(dem, x, y)

                if z is not None:
                    # Отрисовка текста в AutoCAD
                    acad.model.AddText(f"{z:.2f}", APoint(x, y, z), 0.5)
                    points_created += 1

    print(f"Успешно создано точек сетки: {points_created}")


def get_line():
    pass
