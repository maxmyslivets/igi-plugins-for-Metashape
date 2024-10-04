from src.common.startup.initialization import ms, import_module


TOP_MENU = 'ИГИ'


def inject():
    from src.shape_transfer.shape_transfer import main
    ms.app.addMenuItem(TOP_MENU + "/" + "Взаимодействие с Autocad" + "/" + "Перенос фигур в Autocad", main)


import_module("Перенос фигур в Autocad", inject)
