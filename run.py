from time import sleep, ticks_ms
import asyncio
from machine import I2C, Pin, SoftI2C, SPI, PWM, Timer, RTC, UART

import network
import socket
import requests
import json

from pn532 import PN532Uart
from mlx90614 import MLX90614_I2C
from max98357 import Player


class Run:

    def __init__(self, is_reload):
        self.ap_ssid = '\uc5b4\ubd80\ubc14 \uc124\uc815'
        self.ap_password = '12341234'

        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''

        self.rtc = RTC()

        self.week_days = ['월', '화', '수', '목', '금', '토', '일']

        self.nfc = PN532Uart(1, tx=Pin(4), rx=Pin(5), debug=False)
        self.nfc.SAM_configuration()

        self.temperature_i2c = SoftI2C(scl=1, sda=0, freq=100000)
        self.temperature_sensor = MLX90614_I2C(self.temperature_i2c, 0x5A)

        self.player = Player()

        self.is_displaying = False
        self.sleep_limit = 300
        self.sleep_time = 0
        self.is_sleeping = False
        self.is_updated = False
        self.is_connected = True

        self.wlan = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

        self.hexadecimal = b'\xFF\xFF\xFF'
        self.display = UART(0, tx=Pin(12), rx=Pin(13), baudrate=115200)

        self.datetime_timer = Timer()
        self.update_timer = Timer()
        self.read_timer = Timer()
        self.wifi_timer = Timer()

        self.run(is_reload)


    def display_send(self, command):
        self.display.write(command)
        self.display.write(self.hexadecimal)
        sleep(0.05)
        response = self.display.read()
        return response


    def display_message(self, msg):
        self.display_send(f'message.msg.txt="{msg}"')


    def display_page(self, page):
        self.display_send(f'page {page}')


    def display_wifi(self, wifi_connected):
        if wifi_connected:
            self.display_send(f'clock.status.pic=2')
            self.display_send(f'nfc_tag.status.pic=2')
            self.display_send(f'message.status.pic=2')
            self.display_send(f'settings.status.pic=2')
        else:
            self.display_send(f'clock.status.pic=3')
            self.display_send(f'nfc_tag.status.pic=3')
            self.display_send(f'message.status.pic=3')
            self.display_send(f'settings.status.pic=3')


    def display_date(self, year, month, day, hour, minute, second, wd_idx):
        yy = self.zfill(f'{year}', '0', 4)
        MM = self.zfill(f'{month}', '0', 2)
        dd = self.zfill(f'{day}', '0', 2)
        hh = self.zfill(f'{hour}', '0', 2)
        mm = self.zfill(f'{minute}', '0', 2)
        ss = self.zfill(f'{second}', '0', 2)
        wd = self.week_days[wd_idx]
        self.display_send(f'clock.date.txt="{yy}년 {MM}월 {dd}일({wd})"')
        self.display_send(f'clock.hour.txt="{hh}"')
        self.display_send(f'clock.minute.txt="{mm}"')
        if second%2:
            self.display_send('clock.colon.txt=""')
        else:
            self.display_send('clock.colon.txt=":"')


    def display_nfc(self, response, temperature):
        result_code = response['resultCode']
        if result_code < 0:
            self.display_message('등록되지 않은 NFC입니다')
            self.display_page('message')
        else:
            name, *_ = response['resultMsg'].split()
            self.display_send(f'name.txt="{name}"')
            self.display_send(f'temp.txt="{temperature}"')
            if result_code >= 3:
                self.display_send('state.txt="하원"')
                self.player.play('02.wav')
            else:
                self.display_send('state.txt="등원"')
                self.player.play('01.wav')
            self.display_page('nfc_tag')
        sleep(1.5)
        self.display_page('clock')


    def update(self):
        f = None
        try:
            f = open('version.txt', 'r')
        except:
            f = open('version.txt', 'w')
            f.close()
            f = open('version.txt', 'r')
        version = f.read()
        f.close()
        self.display_message(f'현재 버전 {version}')
        self.display_page('message')
        sleep(0.5)
        self.display_message('업데이트 확인 중..')

        response = None
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/version.txt')
        except Exception as e:
            self.is_connected = False
            raise e
            return
        print(response.text, version)
        new_version = response.text
        response.close()
        if new_version == version:
            print(f'{version} is latest version.')
            self.display_message(f'현재 최신 버전입니다')
            sleep(1)
            return

        f = open('restore_check.txt', 'w')
        print('writing...')
        f.write('1')
        f.close()
        print('done')
        
        self.display_message(f'{new_version} 업데이트 중..')
        response = None
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/files.txt')
        except:
            self.is_connected = False
            return
        file_names = response.text.split()
        response.close()
        print(file_names)
        for file_name in file_names:
            response = None
            try:
                response = requests.get(f'http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/{file_name}')
                f = open(file_name, 'w')
                f.write(response.text)
                response.close()
                f.close()
            except:
                self.is_connected = False
                return
        
        f = open('restore_check.txt', 'w')
        print('writing...')
        f.write('0')
        f.close()
        print('done')
        
        print('Update complete.')
        self.display_message(f'{new_version} 업데이트 완료')
        sleep(1)
        self.display_message('기기를 재시작합니다')
        self.is_updated = True
        sleep(3)


    def update_handler(self, timer):
        self.update()
        self.display_page('clock')


    def read_handler(self, timer):
        data = self.display.read()
        if data is None:
            return
        self.awake_mode()
        if data == b'e\x00\x06\x01\xff\xff\xff\x04\xff\xff\xff':
            print('settings')
            self.display_page('settings')
            return
        elif data == b'e\x03\x04\x01\xff\xff\xff\x04\xff\xff\xff':
            print('update')
            self.update()
        elif data == b'e\x03\x03\x01\xff\xff\xff\x04\xff\xff\xff':
            print('wifi')
            self.wifi_init(is_init=False)
        elif data == b'e\x03\x02\x01\xff\xff\xff\x04\xff\xff\xff':
            print('back')
        self.display_page('clock')


    def zfill(self, string, char, count):
        return (char*count+string)[-count:]


    def datetime_handler(self, timer):
        year, month, day, wd_idx, hour, minute, second = self.rtc.datetime()[:7]
        if not self.is_displaying and self.sleep_time < self.sleep_limit:
            self.sleep_time += 1
        if not self.is_sleeping and self.sleep_time >= self.sleep_limit:
            self.sleep_mode()
        if self.is_displaying or self.is_sleeping:
            return
        self.display_date(year, month, day, hour, minute, second, wd_idx)
    

    def wifi_handler(self, timer):
        self.display_wifi(self.wlan.isconnected())


    def web_login_page(self, network_list):
        html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
                <body><h1>어부바 전자출결기기 Wi-fi 설정</h1>
                <form><label for="ssid">그룹 ID(GROUP_ID): <input id="groupId" name="groupId"><br></label>
                <label for="ssid">와이파이 이름: <select id="ssid" name="ssid">"""
        html += ''.join([f'<option value="{network_name}">{network_name}</option>' for network_name in network_list])
        html += """</select><br></label>
                <label for="password">와이파이 비밀번호: <input id="password" name="password" type="password"></label><br>
                <input hidden name="end">
                <input type="submit" value="확인"></form></body></html>
                """
        return html


    def web_done_page(self):
        html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
                <body><h1>설정 완료</h1></body></html>
            """
        return html


    def wifi_setting(self, is_wrong):
        self.wlan.active(False)
        self.wlan.disconnect()
        sleep(0.5)

        self.ap.active(False)
        self.ap.disconnect()
        sleep(0.5)

        self.display_wifi(self.wlan.isconnected())
        
        f = None
        try:
            f = open('wifi_data.txt', 'r')
        except:
            f = open('wifi_data.txt', 'w')
            f.close()
            f = open('wifi_data.txt', 'r')
        print('file read...')
        data = f.read()
        f.close()
            
        if data.find('$') >= 0:
            self.kindergarden_id, self.wifi_ssid, self.wifi_password = data.split('$')
        print(self.kindergarden_id, self.wifi_ssid, self.wifi_password)
        
        if self.wifi_ssid != '':
            return
        
        print('wifi setting..')
        
        self.display_page('message')
        if is_wrong:
            self.display_message('와이파이를 확인하세요')
        else:
            self.display_message('와이파이를 설정하세요')

        self.ap.config(essid=self.ap_ssid, password=self.ap_password)
        self.ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '0.0.0.0'))
        self.ap.active(True)
        sleep(0.5)

        network_list = []
        for nw in self.wlan.scan():
            network_list.append(bytes.decode(nw[0]))
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 80))
        s.listen(5)

        timeout_ms = 30000
        end_time = ticks_ms() + timeout_ms

        while self.wifi_ssid == '' and ticks_ms() < end_time:
            conn, addr = s.accept()
            req = str(conn.recv(1024))
            response = self.web_login_page(network_list)
            group_id_idx = req.find('/?groupId=')
            ssid_idx = req.find('&ssid=')
            password_idx = req.find('&password=')
            end_idx = req.find('&end=')
            if ssid_idx >= 0:
                self.kindergarden_id = req[group_id_idx+10:ssid_idx]
                self.wifi_ssid = req[ssid_idx+6:password_idx]
                self.wifi_password = req[password_idx+10:end_idx]
                print(self.kindergarden_id, self.wifi_ssid, self.wifi_password)
                response = self.web_done_page()
            conn.send(response)
            conn.close()
        s.close()
        sleep(0.5)
        self.ap.disconnect()
        sleep(0.5)
                
        f = open('wifi_data.txt', 'w')
        print('writing...')
        f.write(self.kindergarden_id)
        f.write('$')
        f.write(self.wifi_ssid)
        f.write('$')
        f.write(self.wifi_password)
        f.close()
        print('done')


    def wifi_reset(self):
        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''

        f = open('wifi_data.txt', 'w')
        print('Wi-fi init...')
        f.write('')
        f.close()
        print('done')


    def wifi_connect(self):
        self.wlan.active(True)
        
        self.display_message('와이파이 연결 중..')
        self.display_page('message')

        self.wlan.connect(self.wifi_ssid, self.wifi_password)
        count = 0
        while self.wlan.isconnected() == False:
            if count >= 5:
                print('Wi-fi connect fail')
                return False
            print('Wi-fi connecting..')
            count += 1
            sleep(3)
        
        self.display_message('와이파이 연결 완료')
        self.is_connected = True
        print('Wi-fi connect success')
        
        self.display_wifi(self.wlan.isconnected())
        
        print(self.wlan.isconnected())
        print(self.wlan.ifconfig())
        print(self.wlan.status())
        self.ap.active(False)
        sleep(0.5)
        return True


    def wifi_init(self, is_init):
        if not is_init:
            self.wifi_reset()
        self.wifi_setting(is_wrong=False)
        while not self.wifi_connect():
            self.wifi_reset()
            self.wifi_setting(is_wrong=True)
        sleep(0.5)


    def get_temperature(self):
        amb_temp = obj_temp = -100
        while amb_temp > 380 or amb_temp < -70:
            amb_temp = self.temperature_sensor.get_temperature(0)
        while obj_temp > 380 or obj_temp < -70:
            obj_temp = self.temperature_sensor.get_temperature(1)
        temp = obj_temp+3
        print(obj_temp, amb_temp)
        return f'{temp:.1f}'


    def get_time(self):
        response = None
        try:
            response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Seoul')
        except:
            self.is_connected = False
            return
        date = response.json()['datetime']
        year, month, day = map(int, date[:10].split('-'))
        hour, minute, second = map(int, date[11:19].split(':'))
        self.rtc.datetime((year, month, day, 0, hour, minute, second, 0))
        response.close()
        sleep(2)


    async def post_nfc(self, nfc_id):
        headers = {'Content-Type': 'application/json'}
        data = {'nfc_sn': nfc_id, 'seq_kindergarden': self.kindergarden_id}
        print('data')
        print(data)

        response = None
        try:
            response = requests.post('http://api.eobuba.co.kr/nfc', data=json.dumps(data), headers=headers)
        except:
            self.is_connected = False
            return
        result = response.json()
        return response.json()


    def sleep_mode(self):
        self.is_sleeping = True
        self.display_send('sleep=1')


    def awake_mode(self):
        self.is_sleeping = False
        self.sleep_time = 0
        self.display_send('sleep=0')


    def start_datetime_timer(self):
        self.datetime_timer.init(mode=Timer.PERIODIC, period=1000, callback=self.datetime_handler)


    def stop_datetime_timer(self):
        self.datetime_timer.deinit()


    def start_update_timer(self):
        self.update_timer.init(mode=Timer.PERIODIC, period=21600000, callback=self.update_handler)


    def start_read_timer(self):
        self.read_timer.init(mode=Timer.PERIODIC, period=100, callback=self.read_handler)


    def start_wifi_timer(self):
        self.wifi_timer.init(mode=Timer.PERIODIC, period=5000, callback=self.wifi_handler)


    def tag(self):
        self.nfc.SAM_configuration()

        while True:
            if not self.is_connected:
                self.display_message('와이파이 연결 실패')
                self.display_page('message')
                self.wifi_init(is_init=False)
                self.display_page('clock')
            if self.is_updated:
                self.wlan.active(False)
                self.wlan.disconnect()
                sleep(0.5)
                return
            nfc_data = None
            try:
                nfc_data = self.nfc.read_passive_target()
            except Exception as e:
                print('time out')
                continue
            if nfc_data == None:
                continue
            print(nfc_data)
            self.player.play('beep.wav')
            if self.is_sleeping:
                self.awake_mode()
            self.display_message('정보 확인 중..')
            self.display_page('message')
            self.nfc.release_targets()
            nfc_id = ''.join([hex(i)[2:] for i in nfc_data])
            response = asyncio.run(self.post_nfc(nfc_id))
            temperature = self.get_temperature()
            self.display_nfc(response, temperature)


    def run(self, is_reload):
        self.awake_mode()
        self.wifi_init(is_init=True)
        
        self.get_time()

        self.start_datetime_timer()
        self.start_update_timer()
        self.start_read_timer()
        self.start_wifi_timer()

        if not is_reload:
            self.update()

        self.display_page('clock')
        self.tag()
