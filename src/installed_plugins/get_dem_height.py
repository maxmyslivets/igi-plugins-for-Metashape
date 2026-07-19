from src.common.startup.initialization import ms, import_module


TOP_MENU = 'ИГИ'


def inject():
    from src.get_dem_height.get_dem_height import get_point, get_grid, get_line
    ms.app.addMenuItem(TOP_MENU + "/Взаимодействие с Autocad/Получение высоты из ЦММ в Autocad/Точки",
                       get_point)
    ms.app.addMenuItem(TOP_MENU + "/Взаимодействие с Autocad/Получение высоты из ЦММ в Autocad/По сетке",
                       get_grid)
    ms.app.addMenuItem(TOP_MENU + "/Взаимодействие с Autocad/Получение высоты из ЦММ в Autocad/По линии",
                       get_line)


import_module("Получение высоты из ЦММ в Autocad", inject)
