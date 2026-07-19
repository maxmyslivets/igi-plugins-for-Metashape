import Metashape as ms

from pyautocad.api import Autocad
from pyautocad import APoint


def get_dem_height(dem, x, y):
    try:
        return dem.altitude(ms.Vector([x, y]))
    except Exception as e:
        print(e)
        return None


def main():

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
