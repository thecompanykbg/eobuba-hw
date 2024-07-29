# This example demonstrates a UART periperhal.

# This example demonstrates the low-level bluetooth module. For most
# applications, we recommend using the higher-level aioble library which takes
# care of all IRQ handling and connection management. See
# https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble

import bluetooth
import random
import struct
import time
import json

from ble_advertising import advertising_payload
from max98357 import Player

from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTC_INDICATE = const(19)

_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

_ELECTRONIC_ATTENDANCE_UUID = bluetooth.UUID("eab53e40-7d9a-4902-a1e7-630fda98d980")

_NFC_TAG_ID_SYN = (
    bluetooth.UUID("eab53e41-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_NFC_TAG_ID_ACK = (
    bluetooth.UUID("eab53e42-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_WRITE,
)
_KINDERGARDEN_ID_SYN = (
    bluetooth.UUID("eab53e43-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_WRITE,
)
_KINDERGARDEN_ID_ACK = (
    bluetooth.UUID("eab53e44-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_WIFI_SSID_SYN = (
    bluetooth.UUID("eab53e45-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_WRITE,
)
_WIFI_SSID_ACK = (
    bluetooth.UUID("eab53e46-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_WIFI_PASSWORD_SYN = (
    bluetooth.UUID("eab53e47-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_WRITE,
)
_WIFI_PASSWORD_ACK = (
    bluetooth.UUID("eab53e48-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_RESULT_CODE_SYN = (
    bluetooth.UUID("eab53e49-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_WRITE,
)
_RESULT_CODE_ACK = (
    bluetooth.UUID("eab53e50-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_STATE_CODE_SYN = (
    bluetooth.UUID("eab53e51-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_STATE_CODE_ACK = (
    bluetooth.UUID("eab53e52-7d9a-4902-a1e7-630fda98d980"),
    _FLAG_WRITE,
)
_ELECTRONIC_ATTENDANCE_SERVICE = (
    _ELECTRONIC_ATTENDANCE_UUID,
    (
        _NFC_TAG_ID_SYN,
        _NFC_TAG_ID_ACK,
        _KINDERGARDEN_ID_SYN,
        _KINDERGARDEN_ID_ACK,
        _WIFI_SSID_SYN,
        _WIFI_SSID_ACK,
        _WIFI_PASSWORD_SYN,
        _WIFI_PASSWORD_ACK,
        _RESULT_CODE_SYN,
        _RESULT_CODE_ACK,
        _STATE_CODE_SYN,
        _STATE_CODE_ACK
    ),
)


class BLENFC:
    def __init__(self, ble, name='TCS'):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((
            self._handle_nfc_tag_id_syn,
            self._handle_nfc_tag_id_ack,
            self._handle_kindergarden_id_syn,
            self._handle_kindergarden_id_ack,
            self._handle_wifi_ssid_syn,
            self._handle_wifi_ssid_ack,
            self._handle_wifi_password_syn,
            self._handle_wifi_password_ack,
            self._handle_result_code_syn,
            self._handle_result_code_ack,
            self._handle_state_code_syn,
            self._handle_state_code_ack
        ),) = self._ble.gatts_register_services((_ELECTRONIC_ATTENDANCE_SERVICE,))
        self._connections = set()
        self._payload = advertising_payload(name=name, services=[_ELECTRONIC_ATTENDANCE_UUID])
        self._advertise()
        self.player = Player()

    def _irq(self, event, data):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("New connection", conn_handle)
            self._connections.add(conn_handle)
            self.send_state_code('SETTING')
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("Disconnected", conn_handle)
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self._ble.gatts_read(value_handle)
            self.receive(value, value_handle)

    def send_nfc_tag_id(self, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_nfc_tag_id_syn, data)

    def send_state_code(self, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_state_code_syn, data)

    def receive(self, data, value_handle):
        print(data)
        if value_handle == self._handle_kindergarden_id_syn:
            print('kindergarden_id', data)
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._handle_kindergarden_id_ack, data)
        elif value_handle == self._handle_wifi_ssid_syn:
            print('ssid', data)
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._handle_wifi_ssid_ack, data)
        elif value_handle == self._handle_wifi_password_syn:
            print('password', data)
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._handle_wifi_password_ack, data)
        elif value_handle == self._handle_wifi_password_syn:
            print('password', data)
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._handle_wifi_password_ack, data)
        elif value_handle == self._handle_result_code_syn:
            print('resultcode', data)
            if data == 1:
                self.player.play('/sounds/arrive.wav')
            elif data == 3:
                self.player.play('/sounds/leave.wav')
            elif data in [2, 4]:
                self.player.play('/sounds/tag_already.wav')
            elif data == -1:
                self.player.play('/sounds/not_registered.wav')
        elif value_handle == self._handle_nfc_tag_id_ack:
            print('nfc tag id ack', data)
        elif value_handle == self._handle_state_code_ack:
            print('state code ack', data)

    def is_connected(self):
        return len(self._connections) > 0

    def _advertise(self, interval_us=500000):
        print("Starting advertising")
        self._ble.gap_advertise(interval_us, adv_data=self._payload)
