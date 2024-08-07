from time import sleep
from machine import Pin, Timer, reset

import network
import socket
import requests
import json
import ubinascii

from max98357 import Player
from led import LED


class Restore:

    def __init__(self):
        self.led = LED(18, 19, 20)

        self.player = Player()

        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''
        self.version = '0'
        self.error = 0
        self.state = 0    # 0: 정상  1: 와이파이 오류  2: 와이파이 재설정  3: 업데이트 완료
        self.speaker = True

        self.wlan = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

        self.wlan.active(True)
        self.ap_ssid = 'TCS-'+''.join(ubinascii.hexlify(self.wlan.config('mac'), ':').decode().split(':'))[:4].upper()
        self.ap_password = '12341234'
        self.wlan.active(False)

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
                'error': 1,
                'state': 0,
                'speaker': True
            }
            f = open('data.txt', 'w')
            f.write(str(data))
            f.close()

        self.kindergarden_id = data.get('group_id', '')
        self.wifi_ssid = data.get('ssid', '')
        self.wifi_password = data.get('password', '')
        self.error = data.get('error', 1)
        self.state = data.get('state', 0)
        self.speaker = data.get('speaker', True)


    def save_data(self, key, value):
        data = {
            'group_id': self.kindergarden_id,
            'ssid': self.wifi_ssid,
            'password': self.wifi_password,
            'error': self.error,
            'state': self.state,
            'speaker': self.speaker
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
        f.write(new_version)
        f.close()
        print('done')


    def update(self):
        if self.speaker:
            self.player.play('/sounds/updating.wav')

        self.save_data('error', 1)

        response = None
        try:
            response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/version.txt')
        except Exception as e:
            self.save_data('state', 1)
            reset()
        new_version = response.text
        response.close()

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
        if self.speaker:
            self.player.play('/sounds/restart.wav')
        sleep(1)
        reset()


    def web_login_page(self, network_list):
        html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
                <body><h2>어부바 전자출결기기 설정</h2>
                <form><label for="ssid">그룹 ID(GROUP_ID): <input id="groupId" name="groupId"><br></label>
                <label for="ssid">와이파이 이름: <select id="ssid" name="ssid">"""
        html += ''.join([f'<option value="{network_name}">{network_name}</option>' for network_name in network_list])
        html += """</select><br></label>
                <label for="password">와이파이 비밀번호: <input id="password" name="password" type="password"></label><br>
                <label for="speaker-on">스피커 ON <input id="speaker-on" name="speaker" type="radio" value="1"></label>
                <label for="speaker-off">스피커 OFF <input id="speaker-off" name="speaker" type="radio" value="0"></label><br>
                <input hidden name="end">
                <input type="submit" value="확인"></form></body></html>"""
        return html


    def web_done_page(self):
        html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
                <body><h2>설정 완료</h2></body></html>"""
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
            speaker_idx = req.find('&speaker=')
            end_idx = req.find('&end=')
            if ssid_idx >= 0:
                self.kindergarden_id = req[group_id_idx+10:ssid_idx]
                self.wifi_ssid = req[ssid_idx+6:password_idx]
                self.wifi_password = req[password_idx+10:speaker_idx]
                self.speaker = req[speaker_idx+9:end_idx] == '1'
                print(self.kindergarden_id, self.wifi_ssid, self.wifi_password, self.speaker)
                response = self.web_done_page()
                self.save_data('state', 1)
            conn.send(response)
            conn.close()
        s.close()
        sleep(0.5)

        self.ap.disconnect()
        self.is_setting = False
        sleep(0.5)
        reset()


    def wifi_connect(self):
        self.wlan.active(True)
        
        self.wlan.connect(self.wifi_ssid, self.wifi_password)
        count = 0
        if self.speaker:
            self.player.play('/sounds/connecting_wifi.wav')
        while self.wlan.isconnected() == False:
            if count >= 5:
                self.save_data('state', 1)
                reset()
            print('Wi-fi connecting..')
            count += 1
            sleep(3)
        
        print('Wi-fi connect success')
        if self.speaker:
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


    def led_handler(self, timer):
        self.led.set_rgb(255, 0, 0)
        self.led.on()


    def start_led_timer(self):
        self.led_timer.init(mode=Timer.PERIODIC, period=1000, callback=self.led_handler)


    def restore(self):
        self.load_data()

        print('restore', self.error)
        
        if self.error != 0:
            self.wifi_init()
            self.update()
