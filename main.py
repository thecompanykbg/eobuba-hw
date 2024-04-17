import sys
from restore import Restore


Restore()
del Restore


Run = __import__('run').Run
is_reload = False


while True:
    Run(is_reload)
    print('reload')
    del sys.modules['run']
    Run = __import__('run').Run
    is_reload = True
