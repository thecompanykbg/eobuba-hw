from time import sleep
import asyncio
from machine import I2C, Pin, SoftI2C, SPI, PWM, Timer, RTC

import network
import socket
import requests
import json

from pn532 import PN532Uart
from ili9341 import Display, color565
from xglcd_font import XglcdFont
from mlx90614 import MLX90614_I2C


ap_ssid = "Pico_Test"
ap_password = "12341234"

kindergarden_id = wifi_ssid = wifi_password = ''

rtc = RTC()

year = month = day = week_day = hour = minute = second = 0
week_day_str = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

nfc = PN532Uart(1, tx=Pin(4), rx=Pin(5), debug=False)
nfc.SAM_configuration()

temperature_i2c = SoftI2C(scl=1, sda=0, freq=100000)
temperature_sensor = MLX90614_I2C(temperature_i2c, 0x5A)

beeper = PWM(26)
beeper.deinit()

DEBUG = True
VOLUME = 100
is_displaying = False
sleep_limit = 5
sleep_time = 0
is_sleeping = False


# Baud rate of 40000000 seems about the max
spi = SPI(1, baudrate=40000000, sck=Pin(10), mosi=Pin(11))

unispace = XglcdFont('fonts/Unispace12x24.c', 12, 24)
display = Display(spi, dc=Pin(16), cs=Pin(18), rst=Pin(17), rotation=270)


def update():
    try:
        response = requests.get('https://api.eobuba.co.kr/version')
        f = open('version.txt', 'r')
        current_version = f.read()
        f.close()
        if current_version == response.json()['version']:
            print('Latest version.')
            return
        response = requests.get('https://api.eobuba.co.kr/update')
        file_names = resopnse.json()['file_names']
        for file_name in file_names:
            response = requests.get(f'https://api.eobuba.co.kr/update/{file_name}')
            f = open(file_name, 'w')
            print(file_name, 'writing...')
            f.write(response.json()['content'])
            f.close()
            print(file_name, 'done')
        print('Update complete.')
    except Exception as e:
        print(e)
        print('Update is not supported.')


def zfill(string, char, count):
    return (char*count+string)[-count:]


def datetime_handler(timer):
    global year, month, day, week_day, hour, minute, second, sleep_time
    year, month, day, week_day, hour, minute, second = rtc.datetime()[:7]
    if not is_displaying and sleep_time < sleep_limit:
        sleep_time += 1
        print(sleep_time)
    if not is_sleeping and sleep_time >= sleep_limit:
        sleep_mode()
    if is_displaying or is_sleeping:
        return
    yy = zfill(f'{year}', '0', 4)
    MM = zfill(f'{month}', '0', 2)
    dd = zfill(f'{day}', '0', 2)
    hh = zfill(f'{hour}', '0', 2)
    mm = zfill(f'{minute}', '0', 2)
    wd = week_day_str[week_day]
    if second%2:
        display_string(f'{yy}.{MM}.{dd} {hh} {mm} ({wd})')
    else:
        display_string(f'{yy}.{MM}.{dd} {hh}:{mm} ({wd})')
    print(year, month, day, week_day, hour, minute, second)


def web_login_page():
    html = """<html><head><meta charset="utf-8" name="viewport" content="width=device-width, initial-scale=1"></head>
              <body><h1>어부바 전자출결기기 Wi-fi 설정</h1>
              <form><label for="ssid">그룹 ID(GROUP_ID): <input id="groupId" name="groupId"><br></label>
              <label for="ssid">와이파이 이름: <input id="ssid" name="ssid"><br></label>
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


def wifi_setting():
    global kindergarden_id, wifi_ssid, wifi_password
        
    f = open('wifi_data.txt', 'r')
    print('file read...')
    data = f.read()
    f.close()
    if data.find('$') >= 0:
        kindergarden_id, wifi_ssid, wifi_password = data.split('$')
    print(kindergarden_id, wifi_ssid, wifi_password)
    
    if wifi_ssid != '':
        return
    
    clear_display()
    display_string('Please set your Wi-fi.')
    
    ap = network.WLAN(network.AP_IF)
    ap.active(False)

    ap.config(essid=ap_ssid, password=ap_password)
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '0.0.0.0'))

    ap.active(True)
    while ap.active == False:
        pass

    print(ap.ifconfig())

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)

    while wifi_ssid == '':
        conn, addr = s.accept()
        req = str(conn.recv(1024))
        response = web_login_page()
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
    
    f = open('wifi_data.txt', 'w')
    print('writing...')
    f.write(kindergarden_id)
    f.write('$')
    f.write(wifi_ssid)
    f.write('$')
    f.write(wifi_password)
    f.close()
    print('done')


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    clear_display()
    display_string('Wi-fi connecting..')

    wlan.connect(wifi_ssid, wifi_password)
    while wlan.isconnected() == False:
        print('Wi-fi connecting..')
        sleep(3)
    
    clear_display()
    display_string('Wi-fi is connected.')

    print(wlan.isconnected())
    print(wlan.ifconfig())
    print(wlan.status())


def init_display():
    stop_display()
    datetime_handler(None)


def clear_display():
    display.fill_rectangle(0, 0, 320, 240, color565(0, 0, 0))


def display_temperature(temp):
    print(temp)
    display.draw_text(0, 70, f'temperature: {temp}', unispace, color565(255, 128, 0))


def display_string(string):
    display.draw_text(0, 100, f'{string}', unispace, color565(255, 128, 0))


async def beep():
    tempo = 1
    tones = {
        'c': 262,
        'd': 294,
        'e': 330,
        'f': 349,
        'g': 392,
        'a': 440,
        'b': 494,
        'C': 523,
    }
    melody = 'cde'
    rhythm = [1,1,1]
    for tone, length in zip(melody, rhythm):
        beeper.freq(tones[tone])
        beeper.duty_u16(VOLUME)
        await asyncio.sleep(0.2)


async def get_temperature():
    total_temp = 0
    cnt = 0
    while cnt < 5:
        temp = temperature_sensor.get_temperature(1)
        await asyncio.sleep(0.02)
        if temp > 380 or temp < -70:
            continue
        cnt += 1
        total_temp += temp
        print(cnt, temp)
    return f'{total_temp/cnt+3.5:.1f}'


def get_time():
    response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Seoul')
    date = response.json()['datetime']
    year, month, day = map(int, date[:10].split('-'))
    hour, minute, second = map(int, date[11:19].split(':'))
    rtc.datetime((year, month, day, 0, hour, minute, second, 0))


async def post_nfc(nfc_id):
    headers = {'Content-Type': 'application/json'}
    data = {'nfc_sn': nfc_id, 'seq_kindergarden': kindergarden_id}
    print('data')
    print(data)
    response = requests.post('https://api.eobuba.co.kr/nfc', data=json.dumps(data), headers=headers)
    print(response.json())
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
    display.display_off()


def awake_mode():
    global is_sleeping, sleep_time
    is_sleeping = False
    sleep_time = 0
    display.display_on()


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
        start_display()
        clear_display()
        nfc_id = ''.join([hex(i)[2:] for i in nfc_data])
        beep()
        asyncio.run(beep())
        beeper.deinit()
        temp = asyncio.run(get_temperature())
        print('temp', temp)
        display_temperature(temp)
        response = asyncio.run(post_nfc(nfc_id))
        if response['resultCode'] < 0:
            display_string('wrong nfc')
        else:
            display_string(f'welcome, {response['seq_kids']}')
        sleep(2)
        clear_display()
        init_display()


wifi_setting()
wifi_connect()

update()

get_time()

timer = Timer(mode=Timer.PERIODIC, period=1000, callback=datetime_handler)

init_display()
tag()
