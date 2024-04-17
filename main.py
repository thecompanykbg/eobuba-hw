import sys
from restore import Restore


Restore()
del Restore


Run = __import__('run').Run
is_reload = False


while True:
    try:
        Run(is_reload)
    except:
        print('reload')
        del sys.modules['run']
        Run = __import__('run').Run
        is_reload = True
