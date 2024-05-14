from machine import Pin, PWM
from time import sleep


class LED:

    def __init__(self, pin_num):
        self.led = PWM(Pin(pin_num, Pin.OUT))
        self.led.freq(5000)
        self.state = False


    def on(self):
        if not self.state:
            for i in range(0, 65536, 100):
                self.led.duty_u16(i)
                sleep(0.001)
            self.state = True


    def off(self):
        if self.state:
            for i in range(65535, -1, -100):
                self.led.duty_u16(i)
                sleep(0.001)
            self.state = False


    def toggle(self):
        if self.state:
            self.off()
        else:
            self.on()


    def click(self):
        self.led.duty_u16(0)
        sleep(0.1)
        self.led.duty_u16(65535)
        self.state = True
