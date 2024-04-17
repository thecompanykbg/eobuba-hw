from time import sleep
import asyncio
from machine import Pin, UART

import network
import socket
import requests
import json


ap_ssid = "Eobuba NFC"
ap_password = "12341234"

kindergarden_id = wifi_ssid = wifi_password = ''

wlan = network.WLAN(network.STA_IF)
ap = network.WLAN(network.AP_IF)

hexadecimal = b'\xFF\xFF\xFF'
display = UART(0, tx=Pin(12), rx=Pin(13), baudrate=115200)

run()


def display_send(command):
    display.write(command)
    display.write(hexadecimal)
    sleep(0.05)
    response = display.read()
    return response


def display_message(msg):
    display_send(f'message.msg.txt="{msg}"')


def display_page(page):
    display_send(f'page {page}')


def update():
    display_page('message')
    display_message('업데이트 확인 중..')
    f = None
    try:
        f = open('version.txt', 'r')
    except:
        f = open('version.txt', 'w')
        f.close()
        f = open('version.txt', 'r')
    version = f.read()
    response = requests.get('http://raw.githubusercontent.com/thecompanykbg/eobuba-hw/main/version.txt')
    print(response.text, version)
    new_version = response.text
    response.close()
    if new_version == version:
        print(f'{version} is latest version.')
        display_message(f'현재 최신 버전입니다')
        sleep(1)
        return
    
    display_message(f'업데이트 중..')
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
    print('Update complete.')
    display_message(f'{new_version} 업데이트 완료')
    sleep(1)
    display_message('전원을 다시 켜주세요.')
    while True:
        pass


def web_login_page(network_list):
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


def web_done_page():
    html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
              <body><h1>설정 완료</h1></body></html>
           """
    return html


def wifi_setting(is_wrong):
    global kindergarden_id, wifi_ssid, wifi_password
    
    wlan.disconnect()
    sleep(0.5)
    ap.disconnect()
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
        kindergarden_id, wifi_ssid, wifi_password = data.split('$')
    print(kindergarden_id, wifi_ssid, wifi_password)
    
    if wifi_ssid != '':
        return
    
    print('wifi setting..')
    
    display_page('message')
    if is_wrong:
        display_message('와이파이를 확인하세요')
    else:
        display_message('와이파이를 설정하세요')

    ap.config(essid=ap_ssid, password=ap_password)
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '0.0.0.0'))

    ap.active(True)

    print(ap.ifconfig())

    network_list = []
    for nw in wlan.scan():
        network_list.append(bytes.decode(nw[0]))
    wlan.disconnect()
    sleep(0.5)
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)

    while wifi_ssid == '':
        conn, addr = s.accept()
        req = str(conn.recv(1024))
        response = web_login_page(network_list)
        group_id_idx = req.find('/?groupId=')
        ssid_idx = req.find('&ssid=')
        password_idx = req.find('&password=')
        end_idx = req.find('&end=')
        if ssid_idx >= 0:
            kindergarden_id = req[group_id_idx+10:ssid_idx]
            wifi_ssid = req[ssid_idx+6:password_idx]
            wifi_password = req[password_idx+10:end_idx]
            print(kindergarden_id, wifi_ssid, wifi_password)
            response = web_done_page()
        conn.send(response)
        conn.close()
    s.close()
    ap.disconnect()
    sleep(0.5)
    
    f = open('wifi_data.txt', 'w')
    print('writing...')
    f.write(kindergarden_id)
    f.write('$')
    f.write(wifi_ssid)
    f.write('$')
    f.write(wifi_password)
    f.close()
    print('done')


def wifi_reset():
    global kindergarden_id, wifi_ssid, wifi_password
    
    kindergarden_id = wifi_ssid = wifi_password = ''
    
    wlan.disconnect()
    sleep(0.5)
    ap.disconnect()
    sleep(0.5)
    
    f = open('wifi_data.txt', 'w')
    print('Wi-fi init...')
    f.write('')
    f.close()
    print('done')


def wifi_connect():
    wlan.active(True)
    
    display_page('message')
    display_message('와이파이 연결 중..')

    wlan.connect(wifi_ssid, wifi_password)
    count = 0
    while wlan.isconnected() == False:
        if count >= 5:
            print('Wi-fi connect fail')
            return False
        print('Wi-fi connecting..')
        count += 1
        sleep(3)
    
    display_message('와이파이 연결 완료')
    print('Wi-fi connect success')
    
    print(wlan.isconnected())
    print(wlan.ifconfig())
    print(wlan.status())
    sleep(0.5)
    return True


def wifi_init(is_init):
    if not is_init:
        wifi_reset()
    wifi_setting(is_wrong=False)
    while not wifi_connect():
        wifi_reset()
        wifi_setting(is_wrong=True)
    ap.disconnect()
    sleep(0.5)


def repair():
    wifi_init(is_init=True)
    update()
