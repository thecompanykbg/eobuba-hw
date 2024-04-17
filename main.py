from restore import Restore


Restore()
del Restore


from run import Run


while True:
    try:
        Run()
    except:
        print('reload')
