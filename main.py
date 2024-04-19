import sys
from restore import Restore
import gc


Restore()
del Restore


Run = __import__('run').Run
is_reload = False

for key in sys.modules:
    print(key)
    del sys.modules[key]

while True:
    gc.collect()
    Run(is_reload)
    for key in sys.modules:
        print(key)
        del sys.modules[key]
    is_reload = True
    print('reload')
