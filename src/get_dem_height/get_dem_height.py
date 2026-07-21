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

# ----------------------------------------------------------------------
# Асимметричная случайная длина шага
# ----------------------------------------------------------------------
def step_error(step, dec_percent, inc_percent):
    """
    Возвращает длину шага в диапазоне:
    от step * (1 - dec_percent/100) до step * (1 + inc_percent/100).
    Пример: step=20, dec=15%, inc=5% -> [17.0, 21.0]
    """
    min_val = step * (1.0 - dec_percent / 100.0)
    max_val = step * (1.0 + inc_percent / 100.0)
    return random.uniform(min_val, max_val)


# ----------------------------------------------------------------------
# Обновлённый диалог с раздельными процентами уменьшения/увеличения
# ----------------------------------------------------------------------
class GridSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры сетки и шага")
        self.setFixedSize(380, 280)          # увеличена высота под дополнительные поля
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Заголовок
        self.status_label = QtWidgets.QLabel("Шаг 1: Настройте параметры и нажмите 'Далее'")
        self.status_label.setStyleSheet("font-weight: bold; color: #55aaff;")
        layout.addWidget(self.status_label)

        # Шаг сетки
        step_layout = QtWidgets.QHBoxLayout()
        step_label = QtWidgets.QLabel("Расстояние между точками (м):")
        self.step_spinbox = QtWidgets.QDoubleSpinBox()
        self.step_spinbox.setRange(0.1, 1000.0)
        self.step_spinbox.setValue(20.0)
        self.step_spinbox.setDecimals(2)
        step_layout.addWidget(step_label)
        step_layout.addWidget(self.step_spinbox)
        layout.addLayout(step_layout)

        # Учёт направления
        self.align_checkbox = QtWidgets.QCheckBox("Учесть направление (выбрать линию в AutoCAD)")
        layout.addWidget(self.align_checkbox)

        # Разделитель
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)

        # Блок неравномерного шага
        self.error_checkbox = QtWidgets.QCheckBox("Имитировать неравномерный шаг (ходьба человека)")
        layout.addWidget(self.error_checkbox)

        # Параметры асимметричного отклонения
        error_param_layout = QtWidgets.QHBoxLayout()
        error_param_layout.addWidget(QtWidgets.QLabel("Уменьшение, %:"))
        self.dec_percent = QtWidgets.QDoubleSpinBox()
        self.dec_percent.setRange(0.0, 100.0)
        self.dec_percent.setValue(15.0)       # по умолчанию до -15%
        self.dec_percent.setDecimals(1)
        self.dec_percent.setSingleStep(1.0)
        error_param_layout.addWidget(self.dec_percent)
        error_param_layout.addStretch()
        layout.addLayout(error_param_layout)

        inc_param_layout = QtWidgets.QHBoxLayout()
        inc_param_layout.addWidget(QtWidgets.QLabel("Увеличение, %:"))
        self.inc_percent = QtWidgets.QDoubleSpinBox()
        self.inc_percent.setRange(0.0, 100.0)
        self.inc_percent.setValue(5.0)        # по умолчанию до +5%
        self.inc_percent.setDecimals(1)
        self.inc_percent.setSingleStep(1.0)
        inc_param_layout.addWidget(self.inc_percent)
        inc_param_layout.addStretch()
        layout.addLayout(inc_param_layout)

        # Блокировка полей, пока чекбокс не активен
        self.dec_percent.setEnabled(False)
        self.inc_percent.setEnabled(False)
        self.error_checkbox.toggled.connect(self.dec_percent.setEnabled)
        self.error_checkbox.toggled.connect(self.inc_percent.setEnabled)

        layout.addSpacing(10)

        # Кнопка подтверждения
        self.btn_submit = QtWidgets.QPushButton("Далее (Выбрать объекты в AutoCAD)")
        self.btn_submit.clicked.connect(self.accept)
        layout.addWidget(self.btn_submit)

    def get_values(self):
        return {
            "step": self.step_spinbox.value(),
            "align": self.align_checkbox.isChecked(),
            "random_error": self.error_checkbox.isChecked(),
            "dec_percent": self.dec_percent.value(),
            "inc_percent": self.inc_percent.value()
        }


# ----------------------------------------------------------------------
# Основная функция генерации сетки (асимметричное накопление ошибки)
# ----------------------------------------------------------------------
def get_grid():
    print("Запуск генерации сетки высот из ЦММ...")

    chunk = ms.app.document.chunk
    if not chunk or not chunk.elevation:
        ms.app.messageBox("Ошибка: В Metashape отсутствует активный Chunk или ЦММ (DEM).")
        return

    dem = chunk.elevation
    acad = Autocad()

    # Вспомогательная функция выбора объекта в AutoCAD
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

    # Диалог
    app = QtWidgets.QApplication.instance()
    parent_window = app.activeWindow() if app else None
    dialog = GridSettingsDialog(parent=parent_window)

    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        print("Генерация сетки отменена пользователем.")
        return

    ui = dialog.get_values()
    step = ui["step"]
    align_to_line = ui["align"]
    use_random_step = ui["random_error"]
    dec_percent = ui["dec_percent"]
    inc_percent = ui["inc_percent"]

    angle = 0.0

    # Выбор границы
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

    # Выбор направления
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

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    diag = math.hypot(max_x - min_x, max_y - min_y)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # Диапазон шагов
    max_steps = int(diag / step) + 2

    # ================================================================
    # Генерация случайных последовательностей шагов для строк/столбцов
    # ================================================================
    rows = 2 * max_steps + 1   # i от -max_steps до max_steps
    cols = 2 * max_steps + 1   # j

    # row_u[i][j] – накопленная горизонтальная координата для строки i, столбца j
    # i и j здесь локальные индексы от 0 до rows-1, cols-1
    # Удобно сразу хранить в словаре или списке списков.
    row_u = []   # row_u[i] – список длиной cols для строки i
    for i in range(rows):
        # Начинаем с нуля в центральном столбце (индекс centre_col = max_steps)
        # Будем генерировать вправо и влево независимо.
        seq = [0.0] * cols
        centre = max_steps
        # От центра вправо (j > centre)
        for j in range(centre + 1, cols):
            d = step_error(step, dec_percent, inc_percent) if use_random_step else step
            seq[j] = seq[j-1] + d
        # От центра влево (j < centre)
        for j in range(centre - 1, -1, -1):
            d = step_error(step, dec_percent, inc_percent) if use_random_step else step
            seq[j] = seq[j+1] - d   # идём от центра влево, поэтому вычитаем шаг
        row_u.append(seq)

    # col_v[j][i] – вертикальная координата для столбца j, строки i
    col_v = []
    for j in range(cols):
        seq = [0.0] * rows
        centre = max_steps
        # Вниз (i > centre)
        for i in range(centre + 1, rows):
            d = step_error(step, dec_percent, inc_percent) if use_random_step else step
            seq[i] = seq[i-1] + d
        # Вверх (i < centre)
        for i in range(centre - 1, -1, -1):
            d = step_error(step, dec_percent, inc_percent) if use_random_step else step
            seq[i] = seq[i+1] - d
        col_v.append(seq)

    # Индексы в цикле будут от 0 до rows-1, где 0 соответствует -max_steps
    # Преобразование: i_global от -max_steps до max_steps -> i_local = i_global + max_steps
    offset = max_steps

    points_created = 0
    print("Расчет сетки и нанесение высотных отметок...")

    for i_glob in range(-max_steps, max_steps + 1):
        i_loc = i_glob + offset
        for j_glob in range(-max_steps, max_steps + 1):
            j_loc = j_glob + offset

            # Координаты в локальной системе сетки
            u = row_u[i_loc][j_loc]   # горизонталь
            v = col_v[j_loc][i_loc]   # вертикаль

            # Поворот и смещение
            x = center_x + u * cos_a - v * sin_a
            y = center_y + u * sin_a + v * cos_a

            if polygon.contains(Point(x, y)):
                z = get_dem_height(dem, x, y)
                if z is not None:
                    try:
                        acad.model.AddText(f"{z:.2f}", APoint(x, y, z), 0.5)
                        points_created += 1
                    except Exception as pnt_err:
                        print(f"Пропущена точка из-за ошибки COM: {pnt_err}")

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