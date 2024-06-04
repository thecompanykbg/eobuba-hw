from time import sleep, ticks_ms
from machine import Pin, Timer, RTC, reset
import bluetooth

import network
import socket
import requests
import json

from pn532 import PN532Uart
from max98357 import Player
from led import LED


class Run:

    def __init__(self):
        self.ap_ssid = 'TCS'
        self.ap_password = '12341234'

        self.rtc = RTC()

        self.nfc = PN532Uart(1, tx=Pin(4), rx=Pin(5), debug=False)
        self.nfc.SAM_configuration()

        self.player = Player()

        self.led = LED(18, 19, 20)
        self.button = Pin(13, Pin.IN, Pin.PULL_UP)

        self.is_setting = False
        self.is_updating = False

        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''
        self.version = '0'
        self.error = 0
        self.state = 0    # 0: 정상  1: 와이파이 오류  2: 와이파이 재설정  3: 업데이트 완료
        self.button_count = 0

        self.wlan = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

        self.update_timer = Timer()
        self.led_timer = Timer()
        self.button_timer = Timer()

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
        self.error = data.get('error', 1)
        self.state = data.get('state', 0)


    def load_version(self):
        f = version = None
        try:
            f = open('version.txt', 'r')
            version = eval(f.read())
        except:
            version = '0'
            f = open('version.txt', 'w')
            f.write(version)
            f.close()

        self.version = version


    def save_data(self, key, value):
        data = {
            'group_id': self.kindergarden_id,
            'ssid': self.wifi_ssid,
            'password': self.wifi_password,
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


    def save_version(self, new_version):
        print('writing..')
        f = open('version.txt', 'w')
        f.write(str(new_version))
        f.close()
        print('done')
        self.load_version()


    def update(self):
        self.is_updating = True
        self.player.play('/sounds/updating.wav')

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
        self.save_version(new_version)

        print('Update complete.')
        sleep(1)
        reset()


    def update_handler(self, timer):
        self.update()


    def led_handler(self, timer):
        if self.is_updating:
            self.led.set_rgb(255, 0, 0)
            self.led.on()
        elif self.state == 2:
            self.led.set_rgb(255, 0, 0)
            self.led.toggle()
        else:
            self.led.set_rgb(0, 255, 0)
            if self.wlan.isconnected():
                self.led.on()
            else:
                self.led.toggle()


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
        
        if self.state != 2:
            return

        self.is_setting = True
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

        while self.state == 2:
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
                self.save_data('state', 1)
            conn.send(response)
            conn.close()
        s.close()
        sleep(0.5)

        self.ap.disconnect()
        self.is_setting = False
        sleep(0.5)


    def wifi_connect(self):
        self.wlan.active(True)
        
        self.wlan.connect(self.wifi_ssid, self.wifi_password)
        count = 0
        self.player.play('/sounds/connecting_wifi.wav')
        while self.wlan.isconnected() == False:
            if count >= 5:
                self.save_data('state', 1)
                reset()
            print('Wi-fi connecting..')
            count += 1
            sleep(3)
        
        print('Wi-fi connect success')
        self.player.play('/sounds/connected_wifi.wav')
        
        print(self.wlan.isconnected())
        print(self.wlan.ifconfig())
        print(self.wlan.status())
        self.ap.active(False)
        sleep(0.5)
        return True


    def wifi_init(self):
        self.wifi_setting()
        while not self.wifi_connect():
            self.wifi_setting()


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


    def zfill(self, string, char, count):
        return (char*count+string)[-count:]


    def post_nfc(self, nfc_id, is_sound=True):
        year, month, day, wd_idx, hour, minute, second = self.rtc.datetime()[:7]
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
        if not is_sound:
            return
        result_code = result['resultCode']
        if result_code < 0:
            self.player.play('/sounds/not_registered.wav')
        elif result_code == 1:
            self.player.play('/sounds/arrive.wav')
        elif result_code == 3:
            self.player.play('/sounds/leave.wav')
        else:
            self.player.play('/sounds/card_already.wav')


    def button_handler(self, timer):
        if self.state == 2:
            if not self.button.value():
                print('reset')
                self.save_data('state', 1)
                self.led.off()
                reset()
        else:
            if self.button.value():
                self.button_count = 0
                print('count', self.button_count)
            else:
                self.button_count += 1
                if self.button_count >= 3:
                    print('setting')
                    self.save_data('state', 2)
                    self.led.off()
                    reset()


    def start_update_timer(self):
        self.update_timer.init(mode=Timer.PERIODIC, period=21600000, callback=self.update_handler)


    def start_led_timer(self):
        self.led_timer.init(mode=Timer.PERIODIC, period=1000, callback=self.led_handler)


    def start_button_timer(self):
        self.button_timer.init(mode=Timer.PERIODIC, period=1000, callback=self.button_handler)


    def tag(self):
        self.nfc.SAM_configuration()

        while True:
            nfc_data = None
            self.save_data('state', 0)
            try:
                nfc_data = self.nfc.read_passive_target()
            except:
                print('time out')
                continue
            if nfc_data == None:
                continue
            print(nfc_data)
            self.led.click()
            self.player.play('/sounds/beep.wav')
            self.nfc.release_targets()
            nfc_id = ''.join([hex(i)[2:] for i in nfc_data])

            if self.wlan.isconnected():
                print('wifi send', nfc_id)
                self.post_nfc(nfc_id)


    def run(self):
        self.load_data()
        if self.state == 0:
            self.player.play('/sounds/eobuba.wav')
        
        print('data', self.kindergarden_id, self.wifi_ssid, self.wifi_password)

        self.start_led_timer()
        self.start_button_timer()
        print(self.state)
        if self.state == 2:
            self.player.play('/sounds/setting_mode.wav')
        self.wifi_init()

        if self.state == 0:
            self.update()
        self.get_time()
        self.start_update_timer()

        self.tag()
