import sys
from restore import Restore


Restore()
del Restore


del sys.modules['run']
Run = __import__('run').Run


while True:
    try:
        Run()
    except:
        print('reload')
        del sys.modules['run']
        Run = __import__('run').Run
