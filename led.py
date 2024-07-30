from machine import Pin, PWM
from time import sleep


class LED:

    def __init__(self, pin_r, pin_g, pin_b):
        self.led_r = PWM(Pin(pin_r, Pin.OUT))
        self.led_g = PWM(Pin(pin_g, Pin.OUT))
        self.led_b = PWM(Pin(pin_b, Pin.OUT))
        self.led_r.freq(5000)
        self.led_g.freq(5000)
        self.led_b.freq(5000)
        self.r = 0
        self.g = 0
        self.b = 0
        self.volume = 16
        self.state = False


    def set_rgb(self, r, g, b):
        if r == self.r and g == self.g and b == self.b:
            return
        self.r = r
        self.g = g
        self.b = b
        self.off()


    def on(self):
        if not self.state:
            for i in range(256):
                self.led_r.duty_u16(int(self.r*self.volume/256*i))
                self.led_g.duty_u16(int(self.g*self.volume/256*i))
                self.led_b.duty_u16(int(self.b*self.volume/256*i))
                sleep(0.001)
            self.state = True


    def off(self):
        if self.state:
            for i in range(255, -1, -1):
                self.led_r.duty_u16(int(self.r*self.volume/256*i))
                self.led_g.duty_u16(int(self.g*self.volume/256*i))
                self.led_b.duty_u16(int(self.b*self.volume/256*i))
                sleep(0.001)
            self.state = False


    def toggle(self):
        if self.state:
            self.off()
        else:
            self.on()


    def click(self):
        self.led_r.duty_u16(0)
        self.led_g.duty_u16(0)
        self.led_b.duty_u16(0)
        sleep(0.1)
        self.led_r.duty_u16(self.r*self.volume)
        self.led_g.duty_u16(self.g*self.volume)
        self.led_b.duty_u16(self.b*self.volume)
        self.state = True
