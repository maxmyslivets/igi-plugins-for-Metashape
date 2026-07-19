from src.common.startup.initialization import ms, import_module


TOP_MENU = 'ИГИ'


def inject():
    from src.get_dem_height.get_dem_height import main
    ms.app.addMenuItem(TOP_MENU + "/" + "Взаимодействие с Autocad" + "/" + "Получение высоты из ЦММ в Autocad", main)


import_module("Получение высоты из ЦММ в Autocad", inject)
