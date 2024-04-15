from time import sleep
import asyncio
from machine import I2C, Pin, SoftI2C, SPI, PWM, Timer, RTC, UART

import network
import socket
import requests
import json

from pn532 import PN532Uart
from mlx90614 import MLX90614_I2C


ap_ssid = "Eobuba NFC"
ap_password = "12341234"

kindergarden_id = wifi_ssid = wifi_password = ''

rtc = RTC()

week_days = ['월', '화', '수', '목', '금', '토', '일']

nfc = PN532Uart(1, tx=Pin(4), rx=Pin(5), debug=False)
nfc.SAM_configuration()

temperature_i2c = SoftI2C(scl=1, sda=0, freq=100000)
temperature_sensor = MLX90614_I2C(temperature_i2c, 0x5A)

beeper = PWM(26)
beeper.deinit()

DEBUG = True
VOLUME = 20
is_displaying = False
sleep_limit = 300
sleep_time = 0
is_sleeping = False

wlan = network.WLAN(network.STA_IF)
ap = network.WLAN(network.AP_IF)

hexadecimal = b'\xFF\xFF\xFF'
display = UART(0, tx=Pin(12), rx=Pin(13), baudrate=115200)

datetime_timer = Timer()
update_timer = Timer()
read_timer = Timer()


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


def display_date(year, month, day, hour, minute, second, wd_idx):
    yy = zfill(f'{year}', '0', 4)
    MM = zfill(f'{month}', '0', 2)
    dd = zfill(f'{day}', '0', 2)
    hh = zfill(f'{hour}', '0', 2)
    mm = zfill(f'{minute}', '0', 2)
    ss = zfill(f'{second}', '0', 2)
    wd = week_days[wd_idx]
    display_send(f'date.txt="{yy}년 {MM}월 {dd}일({wd})"')
    display_send(f'hour.txt="{hh}"')
    display_send(f'minute.txt="{mm}"')
    if second%2:
        display_send('colon.txt=""')
    else:
        display_send('colon.txt=":"')


def display_nfc(response, temperature):
    result_code = response['resultCode']
    if result_code < 0:
        display_page('message')
        display_message('등록되지 않은 NFC입니다')
    else:
        name, *_ = response['resultMsg'].split()
        display_page('nfc_tag')
        display_send(f'name.txt="{name}"')
        display_send(f'temp.txt="{temperature}"')
        if result_code >= 3:
            display_send('state.txt="하원"')
        else:
            display_send('state.txt="등원"')
    sleep(1)
    display_page('clock')


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


def update_handler(timer):
    update()
    display_page('clock')


def read_handler(timer):
    data = display.read()
    if data is None:
        return
    if data == b'e\x00\x06\x01\xff\xff\xff\x04\xff\xff\xff':
        print('settings')
        display_page('settings')
        return
    elif data == b'e\x03\x03\x01\xff\xff\xff\x04\xff\xff\xff':
        print('wifi')
        wifi_init(is_init=False)
    elif data == b'e\x03\x04\x01\xff\xff\xff\x04\xff\xff\xff':
        print('update')
        update()
    elif data == b'e\x03\x02\x01\xff\xff\xff\x04\xff\xff\xff':
        print('back')
    display_page('clock')


def zfill(string, char, count):
    return (char*count+string)[-count:]


def datetime_handler(timer):
    global sleep_time
    year, month, day, wd_idx, hour, minute, second = rtc.datetime()[:7]
    if not is_displaying and sleep_time < sleep_limit:
        sleep_time += 1
    if not is_sleeping and sleep_time >= sleep_limit:
        sleep_mode()
    if is_displaying or is_sleeping:
        return
    display_date(year, month, day, hour, minute, second, wd_idx)


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


def beep():
    beeper.freq(440)
    beeper.duty_u16(VOLUME)
    sleep(0.1)
    beeper.deinit()


def get_temperature():
    temp = 0
    while True:
        temp = temperature_sensor.get_temperature(1)
        if temp > 380 or temp < -70:
            continue
        break
    print(temp)
    return f'{temp+3.5:.1f}'


def get_time():
    response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Seoul')
    date = response.json()['datetime']
    year, month, day = map(int, date[:10].split('-'))
    hour, minute, second = map(int, date[11:19].split(':'))
    rtc.datetime((year, month, day, 0, hour, minute, second, 0))
    response.close()
    sleep(2)


async def post_nfc(nfc_id):
    headers = {'Content-Type': 'application/json'}
    data = {'nfc_sn': nfc_id, 'seq_kindergarden': kindergarden_id}
    print('data')
    print(data)
    response = requests.post('http://api.eobuba.co.kr/nfc', data=json.dumps(data), headers=headers)
    result = response.json()
    return response.json()


def start_display():
    global is_displaying
    is_displaying = True


def stop_display():
    global is_displaying
    is_displaying = False


def sleep_mode():
    global is_sleeping
    is_sleeping = True
    display_send('sleep=1')


def awake_mode():
    global is_sleeping, sleep_time
    is_sleeping = False
    sleep_time = 0
    display_send('sleep=0')


def start_datetime_timer():
    datetime_timer.init(mode=Timer.PERIODIC, period=1000, callback=datetime_handler)


def stop_datetime_timer():
    datetime_timer.deinit()


def start_update_timer():
    update_timer.init(mode=Timer.PERIODIC, period=21600000, callback=update_handler)


def start_read_timer():
    read_timer.init(mode=Timer.PERIODIC, period=100, callback=read_handler)


def tag():
    nfc.SAM_configuration()

    while True:
        nfc_data = None
        try:
            nfc_data = nfc.read_passive_target()
        except Exception as e:
            nfc.release_targets()
            print('time out')
            continue
        if nfc_data == None:
            continue
        print(nfc_data)
        if is_sleeping:
            awake_mode()
        display_page('message')
        display_message('정보 확인 중..')
        nfc_id = ''.join([hex(i)[2:] for i in nfc_data])
        beep()
        response = asyncio.run(post_nfc(nfc_id))
        temperature = get_temperature()
        display_nfc(response, temperature)


awake_mode()

wifi_init(is_init=True)

get_time()

start_datetime_timer()
start_update_timer()
start_read_timer()

update()

display_page('clock')
tag()
