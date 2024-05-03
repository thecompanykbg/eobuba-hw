from time import sleep
import asyncio
from machine import I2C, Pin, SPI, PWM, Timer, RTC, UART, reset

import network
import socket
import requests
import json

from pn532 import PN532Uart
from max98357 import Player


class Run:

    def __init__(self):
        self.ap_ssid = '\uc5b4\ubd80\ubc14 \uc124\uc815'
        self.ap_password = '12341234'

        self.rtc = RTC()

        self.nfc = PN532Uart(1, tx=Pin(4), rx=Pin(5), debug=False)
        self.nfc.SAM_configuration()

        self.hexadecimal = b'\xFF\xFF\xFF'
        self.display = UART(0, tx=Pin(12), rx=Pin(13), baudrate=9600)

        self.player = Player()

        self.wifi_led = Pin(17, Pin.OUT)

        self.is_setting = False

        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''
        self.version = '0'
        self.error = 0
        self.state = 0    # 0: 정상  1: 와이파이 오류  2: 와이파이 재설정  3: 업데이트 완료

        self.wlan = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

        self.datetime_timer = Timer()
        self.update_timer = Timer()
        self.wifi_timer = Timer()

        self.run()


    def load_data(self):
        f = data = None
        try:
            f = open('data.txt', 'r')
            data = eval(f.read())
        except:
            data = {
                'group_id': '',
                'ssid': '',
                'password': '',
                'version': '0',
                'brightness': 100,
                'error': 1,
                'state': 0
            }
            f = open('data.txt', 'w')
            f.write(str(data))
            f.close()
        
        self.kindergarden_id = data.get('group_id', '')
        self.wifi_ssid = data.get('ssid', '')
        self.wifi_password = data.get('password', '')
        self.version = data.get('version', '0')
        self.brightness = data.get('brightness', 100)
        self.error = data.get('error', 1)
        self.state = data.get('state', 0)


    def save_data(self, key, value):
        data = {
            'group_id': self.kindergarden_id,
            'ssid': self.wifi_ssid,
            'password': self.wifi_password,
            'version': self.version,
            'brightness': self.brightness,
            'error': self.error,
            'state': self.state
        }
        data[key] = value
        
        print('writing..')
        f = open('data.txt', 'w')
        f.write(str(data))
        f.close()
        print('done')
        self.load_data()


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


    def display_nfc(self, response):
        result_code = response['resultCode']
        if result_code < 0:
            self.display_message('등록되지 않은 카드입니다')
            self.display_page('message')
            self.player.play('/sounds/not_registered.wav')
            self.display_message(f'{response['nfc_sn']}')
            sleep(3)
        else:
            name, *_ = response['resultMsg'].split()
            self.display_send(f'nfc_tag.name.txt="{name}"')
            if result_code >= 3:
                self.display_send('nfc_tag.state.txt="하원"')
            else:
                self.display_send('nfc_tag.state.txt="등원"')
            self.display_page('nfc_tag')
            if result_code == 1:
                self.player.play('/sounds/arrive.wav')
            elif result_code == 3:
                self.player.play('/sounds/leave.wav')
            else:
                self.player.play('/sounds/card_already.wav')
        self.display_page('clock')


    def update(self):
        response = None
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/version.txt')
        except Exception as e:
            self.save_data('state', 1)
            reset()
        print(response.text, self.version)
        new_version = response.text
        response.close()
        if new_version == self.version:
            print(f'{self.version} is latest version.')
            sleep(0.5)
            return

        self.save_data('error', 1)

        response = None
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/files.txt')
        except Exception as e:
            self.save_data('state', 1)
            reset()
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
            except Exception as e:
                self.save_data('state', 1)
                reset()
        
        self.save_data('error', 0)
        self.save_data('state', 3)
        self.save_data('version', str(new_version))

        print('Update complete.')
        sleep(1)
        reset()


    def update_handler(self, timer):
        self.update()


    def read_handler(self, timer):
        data = self.display.read()
        if data is None:
            return
        self.awake_mode()
        print(data)
        if data == b'e\x00\x06\x01\xff\xff\xff':
            self.start_setting()
            print('settings')
            self.display_page('settings')
            return
        elif data == b'e\x03\x04\x01\xff\xff\xff':
            print('update')
            self.update()
        elif data == b'e\x03\x03\x01\xff\xff\xff':
            print('wifi')
            self.wifi_clear()
            self.wifi_reset()
        elif data == b'e\x03\x06\x01\xff\xff\xff':
            self.display_page('display')
            return
        elif data == b'e\x03\x02\x01\xff\xff\xff':
            print('back')
        elif data == b'e\x04\x02\x01\xff\xff\xff':
            brightness = int.from_bytes(self.display_send('get display.slider.val')[1:3], 'little', True)
            self.set_display_brightness(brightness)
            print('back')
        self.stop_setting()
        self.display_page('clock')


    def load_display_data(self):
        self.display_send(f'display.slider.val={self.brightness}')


    def set_display_brightness(self, brightness):
        self.display_send(f'dims={brightness}')
        print('set brightness', brightness)
        self.save_data('brightness', brightness)


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


    def wifi_time_handler(self, timer):
        if self.wlan.isconnected() and timer is not None:
            self.display_send(f'clock.status.pic={self.wifi_state_time+1}')
            self.display_send(f'nfc_tag.status.pic={self.wifi_state_time+1}')
            self.display_send(f'message.status.pic={self.wifi_state_time+1}')
            self.display_send(f'settings.status.pic={self.wifi_state_time+1}')
            self.display_send(f'display.status.pic={self.wifi_state_time+1}')
            self.wifi_state_time += 1
            if self.wifi_state_time > 2:
                self.wifi_state_time = 0
        else:
            self.wifi_state_time = 0
            self.display_send('clock.status.pic=4')
            self.display_send('nfc_tag.status.pic=4')
            self.display_send('message.status.pic=4')
            self.display_send('settings.status.pic=4')
            self.display_send('display.status.pic=4')


    def web_login_page(self, network_list):
        html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
                <body><h1>어부바 전자출결기기 Wi-fi 설정</h1>
                <form><label for="ssid">그룹 ID(GROUP_ID): <input id="groupId" name="groupId"><br></label>
                <label for="ssid">와이파이 이름: <select id="ssid" name="ssid">"""
        html += ''.join([f'<option value="{network_name}">{network_name}</option>' for network_name in network_list])
        html += """</select><br></label>
                <label for="password">와이파이 비밀번호: <input id="password" name="password" type="password"></label><br>
                <input hidden name="end">
                <input type="submit" value="확인"></form></body></html>"""
        return html


    def web_done_page(self):
        html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
                <body><h1>설정 완료</h1></body></html>"""
        return html


    def wifi_setting(self):
        print(self.kindergarden_id, self.wifi_ssid, self.wifi_password)
        
        if self.wifi_ssid != '':
            return
        
        print('wifi setting..')

        self.wlan.active(False)
        self.ap.config(essid=self.ap_ssid, password=self.ap_password)
        self.ap.ifconfig()
        self.ap.active(True)
        sleep(0.5)

        network_list = []
        try:
            for nw in self.wlan.scan():
                network_list.append(bytes.decode(nw[0]))
        except Exception as e:
            self.save_data('state', 1)
            reset()
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 80))
        s.listen(5)

        while self.wifi_ssid == '':
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

        self.save_data('group_id', self.kindergarden_id)
        self.save_data('ssid', self.wifi_ssid)
        self.save_data('password', self.wifi_password)

        self.ap.disconnect()
        sleep(0.5)


    def wifi_clear(self):
        print('Wi-fi reset...')
        self.wlan.disconnect()
        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''
        self.save_data('kindergarden_id', '')
        self.save_data('ssid', '')
        self.save_data('password', '')


    def wifi_reset(self):
        self.save_data('state', 2)
        reset()


    def wifi_connect(self):
        self.wlan.active(True)
        
        self.wlan.connect(self.wifi_ssid, self.wifi_password)
        count = 0
        while self.wlan.isconnected() == False:
            if count >= 5:
                print('Wi-fi connect fail')
                return False
            print('Wi-fi connecting..')
            count += 1
            sleep(3)
        
        print('Wi-fi connect success')
        
        print(self.wlan.isconnected())
        print(self.wlan.ifconfig())
        print(self.wlan.status())
        self.ap.active(False)
        sleep(0.5)
        return True


    def wifi_init(self):
        self.wifi_setting()
        while not self.wifi_connect():
            self.wifi_clear()
            self.wifi_setting(is_wrong=True)


    def get_time(self):
        response = None
        try:
            response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Seoul')
        except Exception as e:
            self.save_data('state', 1)
            reset()
        date = response.json()['datetime']
        year, month, day = map(int, date[:10].split('-'))
        hour, minute, second = map(int, date[11:19].split(':'))
        self.rtc.datetime((year, month, day, 0, hour, minute, second, 0))
        response.close()


    async def post_nfc(self, nfc_id):
    async def post_nfc(self, nfc_id):
        year, month, day, wd_idx, hour, minute, second = self.rtc.datetime()[:7]
        print(type(hour))
        yy = self.zfill(f'{year}', '0', 4)
        MM = self.zfill(f'{month}', '0', 2)
        dd = self.zfill(f'{day}', '0', 2)
        hh = self.zfill(f'{hour}', '0', 2)
        mm = self.zfill(f'{minute}', '0', 2)
        ss = self.zfill(f'{second}', '0', 2)
        datetime = f'{yy}-{MM}-{dd} {hh}:{mm}:{ss}'
        headers = {'Content-Type': 'application/json'}
        data = {
            'nfc_sn': nfc_id,
            'seq_kindergarden': self.kindergarden_id,
            'version': self.version,
            'inout_type': '1' if hour < 12 else '2',
            'date_time': datetime,
            'result_type': '1'
        }
        print(data)

        response = None
        try:
            response = requests.post('http://api.eobuba.co.kr/nfc', data=json.dumps(data), headers=headers)
        except Exception as e:
            self.save_data('state', 1)
            reset()
        if response is None:
            return
        result = response.json()
        print(result)
        return response.json()


    def start_update_timer(self):
        self.update_timer.init(mode=Timer.PERIODIC, period=21600000, callback=self.update_handler)


    def start_wifi_timer(self):
        self.wifi_timer.init(mode=Timer.PERIODIC, period=1000, callback=self.wifi_handler)


    def start_setting(self):
        self.is_setting = True


    def stop_setting(self):
        self.is_setting = False


    def tag(self):
        self.nfc.SAM_configuration()

        while True:
            if self.is_setting:
                continue
            nfc_data = None
            try:
                nfc_data = self.nfc.read_passive_target()
            except:
                print('time out')
                self.save_data('state', 0)
                continue
            if nfc_data == None:
                continue
            print(nfc_data)
            self.player.play('/sounds/beep.wav')
            self.nfc.release_targets()
            nfc_id = ''.join([hex(i)[2:] for i in nfc_data])
            self.display_message('정보 확인 중..')
            self.display_page('message')
            response = asyncio.run(self.post_nfc(nfc_id))
            self.display_nfc(response)


    def run(self):
        self.load_data()
        if self.state == 0:
            self.player.play('/sounds/eobuba.wav')

        if self.state == 1:
            self.wifi_clear()
            self.wifi_reset()
        else:
            self.wifi_init()
        
        if self.state == 0 or self.state == 1:
            self.update()

        self.get_time()

        self.start_update_timer()
        self.start_wifi_timer()

        self.tag()
