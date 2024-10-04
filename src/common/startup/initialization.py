

ms = None
try:
    import Metashape as ms
except ImportError:
    print("Couldn't find Metashape module, trying to import PhotoScan module instead")
if not ms:
    raise ImportError('PhotoScan module import was failed')


def import_module(plugin_name, inject, subplugin=None):
    try:
        inject()
        if not subplugin:
            print('imported ', plugin_name)
        else:
            print('imported ', subplugin)
    except:
        import traceback
        traceback.print_exc()
