import Metashape as ms

from pyautocad.api import Autocad
from pyautocad import APoint, aDouble
from itertools import chain


def main():

    print('Перенос фигур...')

    chunk = ms.app.document.chunk
    acad = Autocad()

    LAYER_NAME = 'cad_shapes'

    if LAYER_NAME not in [l.name for l in list(acad.doc.Layers)]:
        acad.doc.Layers.Add(LAYER_NAME)

    shapes = [s for s in chunk.shapes.shapes if s.group.label == LAYER_NAME]

    for shape in shapes:
        coords = shape.geometry.coordinates
        if len(coords) == 1 and type(coords[0]) is not list:
            point = acad.model.AddPoint(APoint(coords[0].x, coords[0].y, coords[0].z))
            point.layer = LAYER_NAME
            label = acad.model.AddText(shape.label, APoint(coords[0].x+0.25, coords[0].y-0.25), 0.5)
            label.layer = LAYER_NAME
        elif len(coords) == 1 and type(coords[0]) is list:
            coords_tuple = tuple(chain.from_iterable([(vertex.x, vertex.y, vertex.z) for vertex in coords[0]]))
            polyline_vertex = aDouble(coords_tuple)
            polyline = acad.model.AddPolyline(polyline_vertex)
            polyline.layer = LAYER_NAME
        elif len(coords) > 1:
            coords_tuple = tuple(chain.from_iterable([(vertex.x, vertex.y, vertex.z) for vertex in coords]))
            polyline_vertex = aDouble(coords_tuple)
            polyline = acad.model.AddPolyline(polyline_vertex)
            polyline.layer = LAYER_NAME

    print(f'Успешно перенесено {len(shapes)} фигур.')
