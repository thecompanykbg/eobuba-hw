import wave
from machine import I2S, Pin
from time import sleep


class Player:
    
    def __init__(self):
        # I2S ID
        self.I2S_ID = 0
        # read frame number
        self.READ_FRAME_NUM = 1024
        # I2S buffer size(bytes)
        self.I2S_BUFFER_SIZE = 10000

        # I2S pin number
        self.SCK_PIN = 2
        self.WS_PIN  = self.SCK_PIN + 1 # SCK_PIN number + 1
        self.SD_PIN  = 10
    
    def play(self, file_path):
        # read wave file
        with wave.open(file_path, 'rb') as wave_file:
            
            # get wave file info
            # get channels
            channels = wave_file.getnchannels()
            print('channels:', channels)
            # get framerate
            framerate = wave_file.getframerate()
            print('framerate:', framerate)
            # get sample size(bits). getsampwidth() return bytes, and 1bytes is 8bits. 
            sample_size = wave_file.getsampwidth() * 8
            print('sample_size(bits):', sample_size)
            # get frame number
            frame_num = wave_file.getnframes()
            print('frame_num:', frame_num)
            
            # set mono or stereo
            if channels == 1:
                # channels == 1 is mono
                mode = I2S.MONO
            else:
                # channels == 2 is stereo
                mode = I2S.STEREO
            
            # create I2S instance
            i2s = I2S(self.I2S_ID, sck=Pin(self.SCK_PIN), ws=Pin(self.WS_PIN), sd=Pin(self.SD_PIN),
                      mode=I2S.TX, bits=sample_size, format=mode, rate=framerate, ibuf=self.I2S_BUFFER_SIZE)
            
            # read audio data
            audio_data = wave_file.readframes(self.READ_FRAME_NUM)
            # repeat till audio data exist
            while audio_data:
                # write audio data to I2S
                i2s.write(audio_data)
                # read audio data
                audio_data = wave_file.readframes(self.READ_FRAME_NUM)
            sleep(0.8)

            # stop I2S
            i2s.deinit()
