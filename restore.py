from time import sleep
from machine import Pin, Timer, reset

import network
import socket
import requests
import json


class Restore:

    def __init__(self):
        self.ap_ssid = '\uc5b4\ubd80\ubc14 \uc124\uc815'
        self.ap_password = '12341234'

        self.ble_led = Pin(21, Pin.OUT)
        self.wifi_led = Pin(17, Pin.OUT)

        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''
        self.version = '0'
        self.mode = 0     # 0: 와이파이  1: 블루투스
        self.error = 0
        self.state = 0    # 0: 정상  1: 와이파이 오류  2: 와이파이 재설정  3: 업데이트 완료

        self.wlan = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

        self.led_timer = Timer()

        self.restore()


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
                'mode': 0,
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
        self.mode = data.get('mode', 0)
        self.error = data.get('error', 1)
        self.state = data.get('state', 0)


    def save_data(self, key, value):
        data = {
            'group_id': self.kindergarden_id,
            'ssid': self.wifi_ssid,
            'password': self.wifi_password,
            'version': self.version,
            'mode': self.mode,
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


    def update(self):
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/version.txt')
        except Exception as e:
            reset()
        print(response.text, self.version)
        new_version = response.text
        response.close()

        self.save_data('error', 1)
        
        response = None
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/files.txt')
        except Exception as e:
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
                reset()
        
        self.save_data('error', 0)
        self.save_data('state', 3)
        self.save_data('version', str(new_version))
        
        print('Update complete.')
        reset()


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
        for nw in self.wlan.scan():
            network_list.append(bytes.decode(nw[0]))
        
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
        self.start_wifi_time_timer()
        
        print(self.wlan.isconnected())
        print(self.wlan.ifconfig())
        print(self.wlan.status())
        self.ap.active(False)
        sleep(0.5)
        return True


    def wifi_init(self):
        self.wifi_setting(is_wrong=False)
        while not self.wifi_connect():
            self.wifi_clear()
            self.wifi_setting(is_wrong=True)


    def led_handler(self, timer):
        if self.wlan.isconnected():
            self.wifi_led.value(1)
            self.ble_led.value(0)
        else:
            self.wifi_led.toggle()
            self.ble_led.value(0)


    def start_led_timer(self):
        self.led_timer.init(mode=Timer.PERIODIC, period=1000, callback=self.led_handler)


    def restore(self):
        self.load_data()

        print('restore', self.error)
        
        if self.error != 0:
            if self.state == 1:
                self.wifi_clear()
                self.wifi_reset()
            else:
                self.wifi_init()
                self.update()
