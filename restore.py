from time import sleep
from machine import Pin, UART

import network
import socket
import requests
import json


class Restore:

    def __init__(self):
        self.ap_ssid = '\uc5b4\ubd80\ubc14 \uc124\uc815'
        self.ap_password = '12341234'

        self.kindergarden_id = self.wifi_ssid = self.wifi_password = ''

        self.is_displaying = False

        self.wlan = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)

        self.hexadecimal = b'\xFF\xFF\xFF'
        self.display = UART(0, tx=Pin(12), rx=Pin(13), baudrate=115200)

        self.restore()


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
        self.display_page('message')
        self.display_message('업데이트를 재개합니다')
        sleep(0.5)
        self.display_message('업데이트 확인 중..')
        response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/version.txt')
        print(response.text, version)
        new_version = response.text
        response.close()
        
        f = open('update_check.txt', 'w')
        print('writing...')
        f.write('1')
        f.close()
        print('done')
        
        self.display_message(f'업데이트 중..')
        response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/files.txt')
        file_names = response.text.split()
        response.close()
        print(file_names)
        for file_name in file_names:
            response = requests.get(f'http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/{file_name}')
            f = open(file_name, 'w')
            f.write(response.text)
            response.close()
            f.close()
        
        f = open('update_check.txt', 'w')
        print('writing...')
        f.write('0')
        f.close()
        print('done')
        
        print('Update complete.')
        self.display_message(f'{new_version} 업데이트 완료')
        sleep(1)
        self.display_message('전원을 다시 켜주세요.')
        while True:
            pass


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

        self.ap.active(True)
        self.ap.config(essid=self.ap_ssid, password=self.ap_password)
        self.ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '0.0.0.0'))

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
        
        self.display_page('message')
        self.display_message('와이파이 연결 중..')

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
        print('Wi-fi connect success')
        
        print(self.wlan.isconnected())
        print(self.wlan.ifconfig())
        print(self.wlan.status())
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


    def sleep_mode(self):
        self.is_sleeping = True
        self.display_send('sleep=1')


    def awake_mode(self):
        self.is_sleeping = False
        self.sleep_time = 0
        self.display_send('sleep=0')


    def restore(self):
        f = None
        try:
            f = open('restore_check.txt', 'r')
        except:
            f = open('restore_check.txt', 'w')
            f.close()
            f = open('restore_check.txt', 'r')
        print('restore check..')
        data = f.read()
        f.close()
        print(data)
        
        if data != '0':
            self.wifi_init(is_init=True)
            self.update()
