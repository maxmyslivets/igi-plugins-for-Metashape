import os
import glob


plugins_in_dir = [os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.dirname(__file__)+"/*.py")]

__all__ = plugins_in_dir
