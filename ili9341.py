from time import sleep
from math import cos, sin, pi, radians
from sys import implementation
from framebuf import FrameBuffer, RGB565  # type: ignore
from micropython import const  # type: ignore


def color565(r, g, b):
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3


class Display(object):
    # Command constants from ILI9341 datasheet
    NOP = const(0x00)  # No-op
    SWRESET = const(0x01)  # Software reset
    RDDID = const(0x04)  # Read display ID info
    RDDST = const(0x09)  # Read display status
    SLPIN = const(0x10)  # Enter sleep mode
    SLPOUT = const(0x11)  # Exit sleep mode
    PTLON = const(0x12)  # Partial mode on
    NORON = const(0x13)  # Normal display mode on
    RDMODE = const(0x0A)  # Read display power mode
    RDMADCTL = const(0x0B)  # Read display MADCTL
    RDPIXFMT = const(0x0C)  # Read display pixel format
    RDIMGFMT = const(0x0D)  # Read display image format
    RDSELFDIAG = const(0x0F)  # Read display self-diagnostic
    INVOFF = const(0x20)  # Display inversion off
    INVON = const(0x21)  # Display inversion on
    GAMMASET = const(0x26)  # Gamma set
    DISPLAY_OFF = const(0x28)  # Display off
    DISPLAY_ON = const(0x29)  # Display on
    SET_COLUMN = const(0x2A)  # Column address set
    SET_PAGE = const(0x2B)  # Page address set
    WRITE_RAM = const(0x2C)  # Memory write
    READ_RAM = const(0x2E)  # Memory read
    PTLAR = const(0x30)  # Partial area
    VSCRDEF = const(0x33)  # Vertical scrolling definition
    MADCTL = const(0x36)  # Memory access control
    VSCRSADD = const(0x37)  # Vertical scrolling start address
    PIXFMT = const(0x3A)  # COLMOD: Pixel format set
    WRITE_DISPLAY_BRIGHTNESS = const(0x51)  # Brightness hardware dependent!
    READ_DISPLAY_BRIGHTNESS = const(0x52)
    WRITE_CTRL_DISPLAY = const(0x53)
    READ_CTRL_DISPLAY = const(0x54)
    WRITE_CABC = const(0x55)  # Write Content Adaptive Brightness Control
    READ_CABC = const(0x56)  # Read Content Adaptive Brightness Control
    WRITE_CABC_MINIMUM = const(0x5E)  # Write CABC Minimum Brightness
    READ_CABC_MINIMUM = const(0x5F)  # Read CABC Minimum Brightness
    FRMCTR1 = const(0xB1)  # Frame rate control (In normal mode/full colors)
    FRMCTR2 = const(0xB2)  # Frame rate control (In idle mode/8 colors)
    FRMCTR3 = const(0xB3)  # Frame rate control (In partial mode/full colors)
    INVCTR = const(0xB4)  # Display inversion control
    DFUNCTR = const(0xB6)  # Display function control
    PWCTR1 = const(0xC0)  # Power control 1
    PWCTR2 = const(0xC1)  # Power control 2
    PWCTRA = const(0xCB)  # Power control A
    PWCTRB = const(0xCF)  # Power control B
    VMCTR1 = const(0xC5)  # VCOM control 1
    VMCTR2 = const(0xC7)  # VCOM control 2
    RDID1 = const(0xDA)  # Read ID 1
    RDID2 = const(0xDB)  # Read ID 2
    RDID3 = const(0xDC)  # Read ID 3
    RDID4 = const(0xDD)  # Read ID 4
    GMCTRP1 = const(0xE0)  # Positive gamma correction
    GMCTRN1 = const(0xE1)  # Negative gamma correction
    DTCA = const(0xE8)  # Driver timing control A
    DTCB = const(0xEA)  # Driver timing control B
    POSC = const(0xED)  # Power on sequence control
    ENABLE3G = const(0xF2)  # Enable 3 gamma control
    PUMPRC = const(0xF7)  # Pump ratio control

    ROTATE = {
        0: 0x88,
        90: 0xE8,
        180: 0x48,
        270: 0x28
    }

    def __init__(self, spi, cs, dc, rst, width=240, height=320, rotation=0,
                 bgr=True, gamma=True):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.width = width
        self.height = height
        if rotation not in self.ROTATE.keys():
            raise RuntimeError('Rotation must be 0, 90, 180 or 270.')
        else:
            self.rotation = self.ROTATE[rotation]
            if not bgr:  # Clear BGR bit
                self.rotation &= 0b11110111

        # Initialize GPIO pins and set implementation specific methods
        if implementation.name == 'circuitpython':
            self.cs.switch_to_output(value=True)
            self.dc.switch_to_output(value=False)
            self.rst.switch_to_output(value=True)
            self.reset = self.reset_cpy
            self.write_cmd = self.write_cmd_cpy
            self.write_data = self.write_data_cpy
        else:
            self.cs.init(self.cs.OUT, value=1)
            self.dc.init(self.dc.OUT, value=0)
            self.rst.init(self.rst.OUT, value=1)
            self.reset = self.reset_mpy
            self.write_cmd = self.write_cmd_mpy
            self.write_data = self.write_data_mpy
        self.reset()
        # Send initialization commands
        self.write_cmd(self.SWRESET)  # Software reset
        sleep(.1)
        self.write_cmd(self.PWCTRB, 0x00, 0xC1, 0x30)  # Pwr ctrl B
        self.write_cmd(self.POSC, 0x64, 0x03, 0x12, 0x81)  # Pwr on seq. ctrl
        self.write_cmd(self.DTCA, 0x85, 0x00, 0x78)  # Driver timing ctrl A
        self.write_cmd(self.PWCTRA, 0x39, 0x2C, 0x00, 0x34, 0x02)  # Pwr ctrl A
        self.write_cmd(self.PUMPRC, 0x20)  # Pump ratio control
        self.write_cmd(self.DTCB, 0x00, 0x00)  # Driver timing ctrl B
        self.write_cmd(self.PWCTR1, 0x23)  # Pwr ctrl 1
        self.write_cmd(self.PWCTR2, 0x10)  # Pwr ctrl 2
        self.write_cmd(self.VMCTR1, 0x3E, 0x28)  # VCOM ctrl 1
        self.write_cmd(self.VMCTR2, 0x86)  # VCOM ctrl 2
        self.write_cmd(self.MADCTL, self.rotation)  # Memory access ctrl
        self.write_cmd(self.VSCRSADD, 0x00)  # Vertical scrolling start address
        self.write_cmd(self.PIXFMT, 0x55)  # COLMOD: Pixel format
        self.write_cmd(self.FRMCTR1, 0x00, 0x18)  # Frame rate ctrl
        self.write_cmd(self.DFUNCTR, 0x08, 0x82, 0x27)
        self.write_cmd(self.ENABLE3G, 0x00)  # Enable 3 gamma ctrl
        self.write_cmd(self.GAMMASET, 0x01)  # Gamma curve selected
        if gamma:  # Use custom gamma correction values
            self.write_cmd(self.GMCTRP1, 0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08,
                           0x4E, 0xF1, 0x37, 0x07, 0x10, 0x03, 0x0E, 0x09,
                           0x00)
            self.write_cmd(self.GMCTRN1, 0x00, 0x0E, 0x14, 0x03, 0x11, 0x07,
                           0x31, 0xC1, 0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36,
                           0x0F)
        self.write_cmd(self.SLPOUT)  # Exit sleep
        sleep(.1)
        self.write_cmd(self.DISPLAY_ON)  # Display on
        sleep(.1)
        #self.cleanup()
        #self.clear()
        self.fill_rectangle(0, 0, 320, 240, color565(0, 0, 0))

    def block(self, x0, y0, x1, y1, data):
        self.write_cmd(self.SET_COLUMN,
                       x0 >> 8, x0 & 0xff, x1 >> 8, x1 & 0xff)
        self.write_cmd(self.SET_PAGE,
                       y0 >> 8, y0 & 0xff, y1 >> 8, y1 & 0xff)
        self.write_cmd(self.WRITE_RAM)
        self.write_data(data)

    def cleanup(self):
        self.clear()
        self.display_off()
        self.spi.deinit()
        print('display off')

    def clear(self, color=0, hlines=8):
        w = self.width
        h = self.height
        assert hlines > 0 and h % hlines == 0, ("hlines must be a non-zero factor of height.")
        # Clear display
        if color:
            line = color.to_bytes(2, 'big') * (w * hlines)
        else:
            line = bytearray(w * 2 * hlines)
        for y in range(0, h, hlines):
            self.block(0, y, w - 1, y + hlines - 1, line)

    def display_off(self):
        self.write_cmd(self.DISPLAY_OFF)

    def display_on(self):
        self.write_cmd(self.DISPLAY_ON)

    def draw_hline(self, x, y, w, color):
        if self.is_off_grid(x, y, x + w - 1, y):
            return
        line = color.to_bytes(2, 'big') * w
        self.block(x, y, x + w - 1, y, line)

    def draw_image(self, path, x=0, y=0, w=320, h=240):
        x2 = x + w - 1
        y2 = y + h - 1
        if self.is_off_grid(x, y, x2, y2):
            return
        with open(path, "rb") as f:
            chunk_height = 1024 // w
            chunk_count, remainder = divmod(h, chunk_height)
            chunk_size = chunk_height * w * 2
            chunk_y = y
            if chunk_count:
                for c in range(0, chunk_count):
                    buf = f.read(chunk_size)
                    self.block(x, chunk_y,
                               x2, chunk_y + chunk_height - 1,
                               buf)
                    chunk_y += chunk_height
            if remainder:
                buf = f.read(remainder * w * 2)
                self.block(x, chunk_y,
                           x2, chunk_y + remainder - 1,
                           buf)

    def draw_letter(self, x, y, letter, font, color, background=0,
                    landscape=False, rotate_180=False):
        buf, w, h = font.get_letter(letter, color, background, landscape)
        if rotate_180:
            # Manually rotate the buffer by 180 degrees
            # ensure bytes pairs for each pixel retain color565
            new_buf = bytearray(len(buf))
            num_pixels = len(buf) // 2
            for i in range(num_pixels):
                # The index for the new buffer's byte pair
                new_idx = (num_pixels - 1 - i) * 2
                # The index for the original buffer's byte pair
                old_idx = i * 2
                # Swap the pixels
                new_buf[new_idx], new_buf[new_idx + 1] = buf[old_idx], buf[old_idx + 1]
            buf = new_buf

        # Check for errors (Font could be missing specified letter)
        if w == 0:
            return w, h

        if landscape:
            y -= w
            if self.is_off_grid(x, y, x + h - 1, y + w - 1):
                return 0, 0
            self.block(x, y,
                       x + h - 1, y + w - 1,
                       buf)
        else:
            if self.is_off_grid(x, y, x + w - 1, y + h - 1):
                return 0, 0
            self.block(x, y,
                       x + w - 1, y + h - 1,
                       buf)
        return w, h


    def draw_pixel(self, x, y, color):
        if self.is_off_grid(x, y, x, y):
            return
        self.block(x, y, x, y, color.to_bytes(2, 'big'))


    def draw_rectangle(self, x, y, w, h, color):
        x2 = x + w - 1
        y2 = y + h - 1
        self.draw_hline(x, y, w, color)
        self.draw_hline(x, y2, w, color)
        self.draw_vline(x, y, h, color)
        self.draw_vline(x2, y, h, color)

    def draw_text(self, x, y, text, font, color,  background=0,
                  landscape=False, rotate_180=False, spacing=1):
        iterable_text = reversed(text) if rotate_180 else text
        for letter in iterable_text:
            # Get letter array and letter dimensions
            w, h = self.draw_letter(x, y, letter, font, color, background,
                                    landscape, rotate_180)
            # Stop on error
            if w == 0 or h == 0:
                print('Invalid width {0} or height {1}'.format(w, h))
                return

            if landscape:
                # Fill in spacing
                if spacing:
                    self.fill_hrect(x, y - w - spacing, h, spacing, background)
                # Position y for next letter
                y -= (w + spacing)
            else:
                # Fill in spacing
                if spacing:
                    self.fill_hrect(x + w, y, spacing, h, background)
                # Position x for next letter
                x += (w + spacing)

                # # Fill in spacing
                # if spacing:
                #     self.fill_vrect(x + w, y, spacing, h, background)
                # # Position x for next letter
                # x += w + spacing

    def draw_vline(self, x, y, h, color):
        # Confirm coordinates in boundary
        if self.is_off_grid(x, y, x, y + h - 1):
            return
        line = color.to_bytes(2, 'big') * h
        self.block(x, y, x, y + h - 1, line)

    def fill_hrect(self, x, y, w, h, color):
        if self.is_off_grid(x, y, x + w - 1, y + h - 1):
            return
        chunk_height = 1024 // w
        chunk_count, remainder = divmod(h, chunk_height)
        chunk_size = chunk_height * w
        chunk_y = y
        if chunk_count:
            buf = color.to_bytes(2, 'big') * chunk_size
            for c in range(0, chunk_count):
                self.block(x, chunk_y,
                           x + w - 1, chunk_y + chunk_height - 1,
                           buf)
                chunk_y += chunk_height

        if remainder:
            buf = color.to_bytes(2, 'big') * remainder * w
            self.block(x, chunk_y,
                       x + w - 1, chunk_y + remainder - 1,
                       buf)

    def fill_rectangle(self, x, y, w, h, color):
        if self.is_off_grid(x, y, x + w - 1, y + h - 1):
            return
        if w > h:
            self.fill_hrect(x, y, w, h, color)
        else:
            self.fill_vrect(x, y, w, h, color)


    def fill_vrect(self, x, y, w, h, color):
        if self.is_off_grid(x, y, x + w - 1, y + h - 1):
            return
        chunk_width = 1024 // h
        chunk_count, remainder = divmod(w, chunk_width)
        chunk_size = chunk_width * h
        chunk_x = x
        if chunk_count:
            buf = color.to_bytes(2, 'big') * chunk_size
            for c in range(0, chunk_count):
                self.block(chunk_x, y,
                           chunk_x + chunk_width - 1, y + h - 1,
                           buf)
                chunk_x += chunk_width

        if remainder:
            buf = color.to_bytes(2, 'big') * remainder * h
            self.block(chunk_x, y,
                       chunk_x + remainder - 1, y + h - 1,
                       buf)

    def invert(self, enable=True):
        if enable:
            self.write_cmd(self.INVON)
        else:
            self.write_cmd(self.INVOFF)

    def is_off_grid(self, xmin, ymin, xmax, ymax):
        return False

    def reset_cpy(self):
        self.rst.value = False
        sleep(.05)
        self.rst.value = True
        sleep(.05)

    def reset_mpy(self):
        self.rst(0)
        sleep(.05)
        self.rst(1)
        sleep(.05)

    def scroll(self, y):
        self.write_cmd(self.VSCRSADD, y >> 8, y & 0xFF)

    def set_scroll(self, top, bottom):
        if top + bottom <= self.height:
            middle = self.height - (top + bottom)
            print(top, middle, bottom)
            self.write_cmd(self.VSCRDEF,
                           top >> 8,
                           top & 0xFF,
                           middle >> 8,
                           middle & 0xFF,
                           bottom >> 8,
                           bottom & 0xFF)

    def sleep(self, enable=True):
        if enable:
            self.write_cmd(self.SLPIN)
        else:
            self.write_cmd(self.SLPOUT)

    def write_cmd_mpy(self, command, *args):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([command]))
        self.cs(1)
        # Handle any passed data
        if len(args) > 0:
            self.write_data(bytearray(args))

    def write_cmd_cpy(self, command, *args):
        self.dc.value = False
        self.cs.value = False
        # Confirm SPI locked before writing
        while not self.spi.try_lock():
            pass
        self.spi.write(bytearray([command]))
        self.spi.unlock()
        self.cs.value = True
        # Handle any passed data
        if len(args) > 0:
            self.write_data(bytearray(args))

    def write_data_mpy(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)

    def write_data_cpy(self, data):
        self.dc.value = True
        self.cs.value = False
        # Confirm SPI locked before writing
        while not self.spi.try_lock():
            pass
        self.spi.write(data)
        self.spi.unlock()
        self.cs.value = True
