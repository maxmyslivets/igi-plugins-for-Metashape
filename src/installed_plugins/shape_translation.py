from src.common.startup.initialization import ms, import_module


TOP_MENU = 'ИГИ'


def inject():
    from src.shape_translation.shape_translation import main
    ms.app.addMenuItem(TOP_MENU + "/" + "Взаимодействие с Autocad" + "/" + "Трансляция фигур в Autocad", main)


import_module("Трансляция фигур в Autocad", inject)
