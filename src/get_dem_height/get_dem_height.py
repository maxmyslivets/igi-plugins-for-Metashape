import sys
import subprocess
import math
import random

import Metashape as ms

from PySide2 import QtWidgets, QtCore

try:
    from pyautocad.api import Autocad
    from pyautocad import APoint
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautocad"])
    from pyautocad.api import Autocad
    from pyautocad import APoint

try:
    from shapely.geometry import Point, Polygon, LineString
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "shapely"])
    from shapely.geometry import Point, Polygon, LineString


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


# Создаем класс диалогового окна в стиле Metashape
class GridSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры сетки")
        self.setFixedSize(380, 200)

        # Делаем окно модальным и всегда поверх самого Metashape
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Информационная строка
        self.status_label = QtWidgets.QLabel("Шаг 1: Задайте настройки и нажмите 'Далее'")
        self.status_label.setStyleSheet("font-weight: bold; color: #55aaff;")
        layout.addWidget(self.status_label)

        # Поле ввода шага сетки
        step_layout = QtWidgets.QHBoxLayout()
        step_label = QtWidgets.QLabel("Расстояние между точками сетки (м):")
        self.step_spinbox = QtWidgets.QDoubleSpinBox()
        self.step_spinbox.setRange(0.1, 1000.0)
        self.step_spinbox.setValue(10.0)
        self.step_spinbox.setDecimals(2)
        step_layout.addWidget(step_label)
        step_layout.addWidget(self.step_spinbox)
        layout.addLayout(step_layout)

        # Чекбокс направления
        self.align_checkbox = QtWidgets.QCheckBox("Учесть направление (выбрать линию в AutoCAD)")
        layout.addWidget(self.align_checkbox)

        layout.addSpacing(10)

        # Кнопка подтверждения
        self.btn_submit = QtWidgets.QPushButton("Далее (Выбрать объекты в AutoCAD)")
        self.btn_submit.clicked.connect(self.accept)
        layout.addWidget(self.btn_submit)

    def get_values(self):
        return {
            "step": self.step_spinbox.value(),
            "align": self.align_checkbox.isChecked()
        }


def get_grid():
    print("Запуск генерации сетки высот из ЦММ...")

    chunk = ms.app.document.chunk
    if not chunk or not chunk.elevation:
        ms.app.messageBox("Ошибка: В Metashape отсутствует активный Chunk или ЦММ (DEM).")
        return

    dem = chunk.elevation
    acad = Autocad()

    # Вспомогательная функция для безопасного выбора объекта в AutoCAD
    def get_object_via_set(prompt_text):
        set_name = f"GridSet_{random.randint(1000, 9999)}"
        try:
            sset = acad.doc.SelectionSets.Add(set_name)
        except Exception:
            try:
                sset = acad.doc.SelectionSets.Item(set_name)
                sset.Clear()
            except Exception:
                return None

        print(prompt_text)
        try:
            sset.SelectOnScreen()
            if sset.Count > 0:
                return sset.Item(0)
            return None
        except Exception as e:
            print(f"Ошибка при работе с экраном AutoCAD: {e}")
            return None
        finally:
            try:
                sset.Delete()
            except Exception:
                pass

    # --- Инициализация PySide интерфейса ---
    # Привязываем окно к Metashape MainWindow, чтобы унаследовать тему (Dark/Light)
    app = QtWidgets.QApplication.instance()
    parent_window = app.activeWindow() if app else None

    dialog = GridSettingsDialog(parent=parent_window)

    # exec_() блокирует интерфейс Metashape, пока пользователь не нажмет кнопку
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        print("Генерация сетки отменена пользователем.")
        return

    # Получаем параметры из красивого Qt-окна
    ui_params = dialog.get_values()
    step = ui_params["step"]
    align_to_line = ui_params["align"]
    angle = 0.0

    # --- ВЫБОР ГРАНИЦЫ В AUTOCAD ---
    boundary_obj = get_object_via_set("Выберите ЗАМКНУТУЮ полилинию-границу в AutoCAD...")
    if not boundary_obj or "Polyline" not in boundary_obj.ObjectName:
        ms.app.messageBox("Ошибка: Вы должны выбрать именно ПОЛИЛИНИЮ!")
        return

    coords = boundary_obj.Coordinates
    poly_points = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]

    if len(poly_points) < 3:
        ms.app.messageBox("Ошибка: В полилинии слишком мало вершин!")
        return

    polygon = Polygon(poly_points)
    min_x, min_y, max_x, max_y = polygon.bounds

    # --- ВЫБОР НАПРАВЛЕНИЯ В AUTOCAD ---
    if align_to_line:
        line_obj = get_object_via_set("Выберите ОТРЕЗОК или ПОЛИЛИНИЮ для направления...")
        if line_obj and hasattr(line_obj, 'Coordinates'):
            line_coords = line_obj.Coordinates
            dx = line_coords[2] - line_coords[0]
            dy = line_coords[3] - line_coords[1]
            angle = math.atan2(dy, dx)
            print(f"Угол направления сетки: {math.degrees(angle):.2f}°")
        else:
            print("Направляющая линия не распознана. Угол сброшен на 0°.")

    # --- МАТЕМАТИЧЕСКИЙ РАСЧЕТ И ОТРИСОВКА ---
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    diag = math.hypot(max_x - min_x, max_y - min_y)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    max_steps = int(diag / step) + 2
    points_created = 0

    print("Расчет сетки и нанесение высотных отметок...")

    for i in range(-max_steps, max_steps):
        for j in range(-max_steps, max_steps):
            u = i * step
            v = j * step

            x = center_x + u * cos_a - v * sin_a
            y = center_y + u * sin_a + v * cos_a

            pnt_geo = Point(x, y)
            if polygon.contains(pnt_geo):
                z = get_dem_height(dem, x, y)

                if z is not None:
                    try:
                        # Отрисовка текста в AutoCAD
                        acad.model.AddText(f"{z:.2f}", APoint(x, y, z), 0.5)
                        points_created += 1
                    except Exception as pnt_err:
                        print(f"Пропущена точка из-за занятости шины COM: {pnt_err}")

    print(f"Успешно создано точек сетки: {points_created}")
    ms.app.messageBox(f"Генерация завершена!\nУспешно нанесено точек на чертеж: {points_created}")


# Окно параметров остается прежним
class LineSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры профиля линии")
        self.setFixedSize(380, 200)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.status_label = QtWidgets.QLabel("Задайте максимальный шаг интерполяции вершин:")
        self.status_label.setStyleSheet("font-weight: bold; color: #55aaff;")
        layout.addWidget(self.status_label)

        step_layout = QtWidgets.QHBoxLayout()
        step_label = QtWidgets.QLabel("Макс. расстояние между точками (м):")
        self.step_spinbox = QtWidgets.QDoubleSpinBox()
        self.step_spinbox.setRange(0.5, 10000.0)
        self.step_spinbox.setValue(20.0)
        self.step_spinbox.setDecimals(1)
        step_layout.addWidget(step_label)
        step_layout.addWidget(self.step_spinbox)
        layout.addLayout(step_layout)

        layout.addSpacing(10)
        self.btn_submit = QtWidgets.QPushButton("Выбрать линию в AutoCAD")
        self.btn_submit.clicked.connect(self.accept)
        layout.addWidget(self.btn_submit)

    def get_max_step(self):
        return self.step_spinbox.value()


def get_arc_points(p1, p2, bulge, max_step):
    """
    Математически корректный расчет точек на дуге AutoCAD на основе коэффициента Bulge.
    Учитывает направление обхода (знак bulge) и истинное положение центра окружности.
    """
    points = []
    x1, y1 = p1
    x2, y2 = p2

    # Расстояние между началом и концом дуги (хорда)
    chord = math.hypot(x2 - x1, y2 - y1)
    if chord < 0.001:
        return points

    # Угол дуги (alpha). bulge = tg(alpha / 4)
    alpha = 4 * math.atan(abs(bulge))

    # Радиус дуги (всегда положительный)
    radius = chord / (2 * math.sin(alpha / 2))

    # Стрела прогиба (высота сегмента дуги)
    sagitta = (chord / 2) * abs(bulge)

    # Расстояние от центра хорды до центра окружности
    dist_to_center = radius - sagitta

    # Координаты середины хорды
    cx_chord = (x1 + x2) / 2
    cy_chord = (y1 + y2) / 2

    # Нормализованный вектор хорды
    dx = (x2 - x1) / chord
    dy = (y2 - y1) / chord

    # Смещение к центру окружности идет по перпендикуляру к хорде.
    # Если bulge > 0, дуга идет против часовой стрелки, центр слева от вектора (p1 -> p2).
    # Если bulge < 0, дуга идет по часовой стрелке, центр справа.
    if bulge > 0:
        cx = cx_chord - dy * dist_to_center
        cy = cy_chord + dx * dist_to_center
    else:
        cx = cx_chord + dy * dist_to_center
        cy = cy_chord - dx * dist_to_center

    # Начальный и конечный углы лучей из центра окружности к точкам p1 и p2
    start_angle = math.atan2(y1 - cy, x1 - cx)
    end_angle = math.atan2(y2 - cy, x2 - cx)

    # Расчет точной угловой разницы с учетом знака обхода
    angle_diff = end_angle - start_angle

    if bulge > 0:
        # Против часовой стрелки: разница должна быть положительной
        if angle_diff <= 0:
            angle_diff += 2 * math.pi
    else:
        # По часовой стрелке: разница должна быть отрицательной
        if angle_diff >= 0:
            angle_diff -= 2 * math.pi

    # Полная длина дуги окружности
    arc_len = radius * abs(angle_diff)

    # Расчет количества делений по вашему правилу max_step
    num_divisions = math.ceil(arc_len / max_step)

    # Генерируем только промежуточные точки (исключая концы сегмента)
    for j in range(1, num_divisions):
        t = j / num_divisions
        curr_angle = start_angle + angle_diff * t

        curr_x = cx + radius * math.cos(curr_angle)
        curr_y = cy + radius * math.sin(curr_angle)
        points.append((curr_x, curr_y))

    return points


def get_line():
    print("Запуск расстановки высот по линии с учетом дуг из ЦММ...")

    chunk = ms.app.document.chunk
    if not chunk or not chunk.elevation:
        ms.app.messageBox("Ошибка: В Metashape отсутствует активный Chunk или ЦММ (DEM).")
        return

    dem = chunk.elevation
    acad = Autocad()

    # --- 1. ШАГ: ИНТЕРФЕЙС ПАРАМЕТРОВ ---
    app = QtWidgets.QApplication.instance()
    parent_window = app.activeWindow() if app else None

    dialog = LineSettingsDialog(parent=parent_window)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        print("Операция отменена пользователем.")
        return

    max_step = dialog.get_max_step()

    # --- 2. ШАГ: ВЫБОР ОБЪЕКТА В AUTOCAD ---
    set_name = f"LineSet_{random.randint(1000, 9999)}"
    try:
        sset = acad.doc.SelectionSets.Add(set_name)
    except Exception:
        try:
            sset = acad.doc.SelectionSets.Item(set_name)
            sset.Clear()
        except Exception:
            return

    print("Выберите ПОЛИЛИНИЮ (включая дуговые сегменты) в AutoCAD...")
    try:
        sset.SelectOnScreen()
        if sset.Count == 0:
            ms.app.messageBox("Объект не выбран.")
            return
        line_obj = sset.Item(0)
    except Exception as e:
        print(f"Ошибка выбора: {e}")
        return
    finally:
        try:
            sset.Delete()
        except Exception:
            pass

    points_to_calculate = []

    # --- 3. ШАГ: РАЗБОР ГЕОМЕТРИИ И ОБРАБОТКА ДУГ (BULGE) ---
    try:
        if "Polyline" in line_obj.ObjectName:
            coords = line_obj.Coordinates
            num_vertices = len(coords) // 2

            # Извлекаем плоский список вершин [(x,y), (x,y)...]
            vertices = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]

            # Проверяем, замкнута ли полилиния
            is_closed = line_obj.Closed

            # Определяем количество итераций по сегментам
            num_segments = num_vertices if is_closed else num_vertices - 1

            for i in range(num_segments):
                p1 = vertices[i]
                # Если полилиния замкнута, последний сегмент соединяется с первой вершиной
                p2 = vertices[(i + 1) % num_vertices]

                # Добавляем стартовую вершину сегмента
                points_to_calculate.append(p1)

                # Проверяем наличие прогиба (дуги) у текущего сегмента через API AutoCAD
                # У обычных прямых линий GetBulge(i) возвращает 0.0
                bulge = 0.0
                try:
                    bulge = line_obj.GetBulge(i)
                except Exception:
                    pass  # Для некоторых типов 3D-полилиний метод может отсутствовать

                if abs(bulge) > 0.001:
                    # СЕГМЕНТ ЯВЛЯЕТСЯ ДУГОЙ: Считаем точки по дуге окружности
                    arc_points = get_arc_points(p1, p2, bulge, max_step)
                    points_to_calculate.extend(arc_points)
                else:
                    # СЕГМЕНТ ЯВЛЯЕТСЯ ПРЯМОЙ: Используем стандартное линейное деление
                    segment_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                    if segment_len > max_step:
                        num_divisions = math.ceil(segment_len / max_step)
                        for j in range(1, num_divisions):
                            t = j / num_divisions
                            interp_x = p1[0] + (p2[0] - p1[0]) * t
                            interp_y = p1[1] + (p2[1] - p1[1]) * t
                            points_to_calculate.append((interp_x, interp_y))

            # Если полилиния разомкнута, добавляем самую последнюю точку
            if not is_closed:
                points_to_calculate.append(vertices[-1])

        elif "Line" in line_obj.ObjectName:
            # Обычный отрезок не может иметь дуг, обрабатываем линейно
            start = line_obj.StartPoint
            end = line_obj.EndPoint
            p1, p2 = (start[0], start[1]), (end[0], end[1])

            points_to_calculate.append(p1)
            segment_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if segment_len > max_step:
                num_divisions = math.ceil(segment_len / max_step)
                for j in range(1, num_divisions):
                    t = j / num_divisions
                    points_to_calculate.append((p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t))
            points_to_calculate.append(p2)

        else:
            ms.app.messageBox(f"Тип объекта {line_obj.ObjectName} не поддерживается.")
            return

    except Exception as e:
        print(f"Ошибка анализа геометрии линии: {e}")
        return

    # --- 4. ШАГ: СТРОИТЕЛЬСТВО ОТМЕТОК В AUTOCAD ---
    points_created = 0
    print(f"Расчет высот для {len(points_to_calculate)} точек профиля...")

    for pnt in points_to_calculate:
        x, y = pnt[0], pnt[1]
        z = get_dem_height(dem, x, y)

        if z is not None:
            try:
                # Чертим текст отметки высоты
                acad.model.AddText(f"{z:.2f}", APoint(x, y, z), 0.5)
                points_created += 1
            except Exception as pnt_err:
                print(f"Пропущена точка из-за занятости шины COM: {pnt_err}")

    print(f"Успешно нанесено точек вдоль профиля: {points_created}")
    ms.app.messageBox(f"Расчет окончен!\nНанесено точек (включая дуги): {points_created}")