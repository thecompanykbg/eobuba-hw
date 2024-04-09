# MicroPython IR Temperature Sensor (MLX90640) driver, I2C interface
# Version 1.0
# Published by Embedded Club via www.embedded.club
# Support via what@embedded.club

from micropython import const

# register definitions
MLX90614_SLAVE_ADDR = const(0x5A) #alphanumeric address

MLX90614_TA = const(0x06)
MLX90614_TOBJ1 = const(0x07)
MLX90614_TOBJ2 = const(0x08)

MLX90614_TOMAX = const(0x20)
MLX90614_TOMIN = const(0x21)
MLX90614_PWMCTRL = const(0x22)
MLX90614_TARANGE = const(0x23)
MLX90614_EMISS = const(0x24)
MLX90614_CONFIG = const(0x25)
MLX90614_ADDR = const(0x2E)
MLX90614_ID1 = const(0x3C)
MLX90614_ID2 = const(0x3D)
MLX90614_ID3 = const(0x3E)
MLX90614_ID4 = const(0x3F)

   
class MLX90614_I2C():
    def __init__(self,i2c, addr=MLX90614_SLAVE_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.wbuffer = bytearray(1)
        self.rbuffer = bytearray(3)
        self.read_list = [b"\x00", None]

    def write_cmd(self, cmd):
        self.wbuffer[0] = cmd  
        self.i2c.writeto(self.addr, self.wbuffer, True)
    
    def read_data(self, address):
        self.wbuffer[0] = self.addr<<1 | 0x00
        self.i2c.start()
        self.i2c.write(self.wbuffer)
        self.wbuffer[0] = address
        self.i2c.write(self.wbuffer)

        self.wbuffer[0] = self.addr<<1 | 0x01
        self.i2c.start()
        self.i2c.write(self.wbuffer)
        
        self.i2c.readinto(self.rbuffer,False)
        self.i2c.stop()
        
        return self.rbuffer
          
   # def set_blink_halfhz(self):
   #     self.write_cmd(HT16K33_BLINK_CMD | HT16K33_BLINK_DISPLAYON | (HT16K33_BLINK_HALFHZ<<1))
        
    def get_temperature(self,index):
        data = self.read_data(MLX90614_TA + index)
        temp = data[1]
        temp <<=8
        temp |= data[0]
        temp_inC = 0.02 * temp
        temp_inC -= 273.15
        #print(temp_inC)
        return round(temp_inC,2)

