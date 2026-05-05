import argparse
import os
import struct
import sys
import time
from threading import Thread

import serial.tools.list_ports
import vgamepad as vg

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional; fall back to environment variables or defaults

parser = argparse.ArgumentParser(description='DJI RC-N3 Simulator Gamepad Bridge')
parser.add_argument('-p', '--port', help='Serial port (auto-detect if not specified)')
parser.add_argument('-d', '--debug', action='store_true', help='Show live stick/button values')

args = parser.parse_args()
gamepad = vg.VX360Gamepad()
camera = 0
sequence_number = 0x34eb
SHOW_DEBUG = args.debug or os.environ.get('SHOW_DEBUG', '0') == '1'

# --- Configurable camera buttons via environment / .env ---
BUTTON_MAP = {
    'A': vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    'B': vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    'X': vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    'Y': vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    'START': vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    'BACK': vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    'LB': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    'RB': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    'LS': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    'RS': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    'DPAD_UP': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    'DPAD_DOWN': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    'DPAD_LEFT': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    'DPAD_RIGHT': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}
CAMERA_UP_BUTTON_NAME = os.environ.get('CAMERA_UP_BUTTON', 'Y').upper()
CAMERA_DOWN_BUTTON_NAME = os.environ.get('CAMERA_DOWN_BUTTON', 'B').upper()
if CAMERA_UP_BUTTON_NAME not in BUTTON_MAP:
    CAMERA_UP_BUTTON_NAME = 'Y'
if CAMERA_DOWN_BUTTON_NAME not in BUTTON_MAP:
    CAMERA_DOWN_BUTTON_NAME = 'B'
CAMERA_UP_BUTTON = BUTTON_MAP[CAMERA_UP_BUTTON_NAME]
CAMERA_DOWN_BUTTON = BUTTON_MAP[CAMERA_DOWN_BUTTON_NAME]
CAMERA_SENSITIVITY = int(float(os.environ.get('CAMERA_SENSITIVITY', '0.98')) * 32768)
CAMERA_SENSITIVITY = max(1000, min(CAMERA_SENSITIVITY, 32000))

# --- Configurable physical buttons via environment / .env ---
# RC buttons from cmd_id=0x27 (58-byte response), mapped to gamepad buttons
# Bitmasks from data[28:30] big-endian (verified on RC-N3).
# Mode bits (0x3000) are stripped before checking, so these are button-only masks:
#   Fn=0x0002, Camera=0x0004, Photo=0x0060, RTH=0x0080
# Flight mode switch (3-state, mask 0x3000): Sport=0x0000, Normal=0x1000, Cine=0x2000
RC_BUTTON_DEFS = [
    ('RC_FN_BUTTON',     0x0002, os.environ.get('RC_FN_BUTTON', 'A').upper()),
    ('RC_CAMERA_BUTTON', 0x0004, os.environ.get('RC_CAMERA_BUTTON', 'LB').upper()),
    ('RC_PHOTO_BUTTON',  0x0060, os.environ.get('RC_PHOTO_BUTTON', 'X').upper()),
    ('RC_RTH_BUTTON',    0x0080, os.environ.get('RC_RTH_BUTTON', 'RB').upper()),
]
# Resolve to vgamepad button constants, skip invalid mappings
RC_BUTTONS = []
for name, mask, btn_name in RC_BUTTON_DEFS:
    if btn_name in BUTTON_MAP:
        RC_BUTTONS.append((mask, BUTTON_MAP[btn_name], btn_name))

# Flight mode switch -> optional gamepad button mapping
# When in Sport mode, press the configured button; when in Cine mode, press the other
MODE_SPORT_BUTTON_NAME = os.environ.get('RC_MODE_SPORT_BUTTON', 'START').upper()
MODE_CINE_BUTTON_NAME = os.environ.get('RC_MODE_CINE_BUTTON', 'BACK').upper()
MODE_SPORT_BUTTON = BUTTON_MAP.get(MODE_SPORT_BUTTON_NAME)
MODE_CINE_BUTTON = BUTTON_MAP.get(MODE_CINE_BUTTON_NAME)

# --- Port detection settings ---
DJI_PORT_DESCRIPTIONS = ['DJI USB VCOM For Protocol', 'DEVICE USB VCOM For Protocol']

def calc_checksum(packet, plength):

    crc = [0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
    0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
    0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
    0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
    0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
    0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
    0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
    0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
    0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
    0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
    0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
    0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
    0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
    0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
    0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
    0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
    0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
    0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
    0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
    0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
    0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
    0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
    0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
    0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
    0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
    0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
    0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
    0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
    0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78]

    # Seeds
    # v = 0x1012 #Naza M
    # v = 0x1013 #Phantom 2
    # v = 0x7000 #Naza M V2
    v = 0x3692  #P3/P4/Mavic 

    for i in range(0, plength):
        vv = v >> 8
        v = vv ^ crc[((packet[i] ^ v) & 0xFF)]
    return v

def calc_pkt55_hdr_checksum(seed, packet, plength):
    arr_2A103 = [0x00,0x5E,0xBC,0xE2,0x61,0x3F,0xDD,0x83,0xC2,0x9C,0x7E,0x20,0xA3,0xFD,0x1F,0x41,
        0x9D,0xC3,0x21,0x7F,0xFC,0xA2,0x40,0x1E,0x5F,0x01,0xE3,0xBD,0x3E,0x60,0x82,0xDC,
        0x23,0x7D,0x9F,0xC1,0x42,0x1C,0xFE,0xA0,0xE1,0xBF,0x5D,0x03,0x80,0xDE,0x3C,0x62,
        0xBE,0xE0,0x02,0x5C,0xDF,0x81,0x63,0x3D,0x7C,0x22,0xC0,0x9E,0x1D,0x43,0xA1,0xFF,
        0x46,0x18,0xFA,0xA4,0x27,0x79,0x9B,0xC5,0x84,0xDA,0x38,0x66,0xE5,0xBB,0x59,0x07,
        0xDB,0x85,0x67,0x39,0xBA,0xE4,0x06,0x58,0x19,0x47,0xA5,0xFB,0x78,0x26,0xC4,0x9A,
        0x65,0x3B,0xD9,0x87,0x04,0x5A,0xB8,0xE6,0xA7,0xF9,0x1B,0x45,0xC6,0x98,0x7A,0x24,
        0xF8,0xA6,0x44,0x1A,0x99,0xC7,0x25,0x7B,0x3A,0x64,0x86,0xD8,0x5B,0x05,0xE7,0xB9,
        0x8C,0xD2,0x30,0x6E,0xED,0xB3,0x51,0x0F,0x4E,0x10,0xF2,0xAC,0x2F,0x71,0x93,0xCD,
        0x11,0x4F,0xAD,0xF3,0x70,0x2E,0xCC,0x92,0xD3,0x8D,0x6F,0x31,0xB2,0xEC,0x0E,0x50,
        0xAF,0xF1,0x13,0x4D,0xCE,0x90,0x72,0x2C,0x6D,0x33,0xD1,0x8F,0x0C,0x52,0xB0,0xEE,
        0x32,0x6C,0x8E,0xD0,0x53,0x0D,0xEF,0xB1,0xF0,0xAE,0x4C,0x12,0x91,0xCF,0x2D,0x73,
        0xCA,0x94,0x76,0x28,0xAB,0xF5,0x17,0x49,0x08,0x56,0xB4,0xEA,0x69,0x37,0xD5,0x8B,
        0x57,0x09,0xEB,0xB5,0x36,0x68,0x8A,0xD4,0x95,0xCB,0x29,0x77,0xF4,0xAA,0x48,0x16,
        0xE9,0xB7,0x55,0x0B,0x88,0xD6,0x34,0x6A,0x2B,0x75,0x97,0xC9,0x4A,0x14,0xF6,0xA8,
        0x74,0x2A,0xC8,0x96,0x15,0x4B,0xA9,0xF7,0xB6,0xE8,0x0A,0x54,0xD7,0x89,0x6B,0x35]

    chksum = seed
    for i in range(0, plength):
        chksum = arr_2A103[((packet[i] ^ chksum) & 0xFF)];
    return chksum

def send_duml(s, source, target, cmd_type, cmd_set, cmd_id, payload = None):
    global sequence_number
    packet = bytearray.fromhex(u'55')
    length = 13
    if payload is not None:
        length = length + len(payload)

    if length > 0x3ff:
        print("Packet too large")
        exit(1)

    packet += struct.pack('B', length & 0xff)
    packet += struct.pack('B', (length >> 8) | 0x4) # MSB of length and protocol version
    hdr_crc = calc_pkt55_hdr_checksum(0x77, packet, 3)
    packet += struct.pack('B', hdr_crc)
    packet += struct.pack('B', source)
    packet += struct.pack('B', target)
    packet += struct.pack('<H', sequence_number)
    packet += struct.pack('B', cmd_type)
    packet += struct.pack('B', cmd_set)
    packet += struct.pack('B', cmd_id)

    if payload is not None:
        packet += payload

    crc = calc_checksum(packet, len(packet))
    packet += struct.pack('<H',crc)
    s.write(packet)
    #print(' '.join(format(x, '02x') for x in packet))

    sequence_number = (sequence_number + 1) & 0xFFFF

print('DJI RC-N3 Simulator Gamepad Bridge v4.0.0\n')

# Open serial port (manual override with -p, otherwise auto-detect)
s = None
if args.port:
    try:
        s = serial.Serial(port=args.port, baudrate=115200, timeout=0.005)
        print(f'Opened serial port: {s.name}')
    except (OSError, serial.SerialException) as e:
        print(f'Could not open port {args.port}: {e}')
        exit(1)
else:
    for port in serial.tools.list_ports.comports(True):
        try:
            if any(desc in port.description for desc in DJI_PORT_DESCRIPTIONS):
                port_name = port.name if port.name is not None else port.device
                s = serial.Serial(port=port_name, baudrate=115200, timeout=0.005)
                print(f'Found: {port.description}')
                print(f'Opened serial port: {s.name}')
                break
        except (OSError, serial.SerialException):
            pass

if s is None:
    print('Could not find DJI USB VCOM For Protocol port.')
    print('  - Is the controller connected and powered on?')
    print('  - Is DJI Assistant 2 (Consumer Drones Series) installed?')
    print('  - Make sure DJI Assistant 2 is NOT running at the same time.')
    exit(1)

gamepad.reset()
time.sleep(1)

print('\nDJI RC-N3 gamepad emulation started.')
print(f'  Camera up: {CAMERA_UP_BUTTON_NAME} button  |  Camera down: {CAMERA_DOWN_BUTTON_NAME} button  |  Sensitivity: {CAMERA_SENSITIVITY}')
if RC_BUTTONS:
    mapping = [f'{name.replace("RC_","").replace("_BUTTON","")}={btn_name}' for name, _, btn_name in RC_BUTTON_DEFS if btn_name in BUTTON_MAP]
    print(f'  RC buttons: {"  |  ".join(mapping)}')
    mode_parts = []
    if MODE_SPORT_BUTTON:
        mode_parts.append(f'Sport={MODE_SPORT_BUTTON_NAME}')
    if MODE_CINE_BUTTON:
        mode_parts.append(f'Cine={MODE_CINE_BUTTON_NAME}')
    if mode_parts:
        print(f'  Mode switch: {"  |  ".join(mode_parts)}')
if SHOW_DEBUG:
    print('  Debug output: ON')
else:
    print('  Debug output: OFF (set SHOW_DEBUG=1 in .env or use -d flag)')
print('Close terminal or press Ctrl+C to stop.\n')

# Process input (min 364, center 1024, max 1684) -> (min -32768, center 0, max 32767)
def parseInput(raw_val):
    output = (raw_val - 1024) * 8192 // 165
    if output > 32767:
        return 32767
    if output < -32768:
        return -32768
    return output

st_rh = 0
st_rv = 0
st_lh = 0
st_lv = 0
rc_button_bits = 0  # raw bitmask from cmd_id=0x27
debug_last_display = 0  # throttle debug output

MODE_NAMES = {0x0000: 'Sport', 0x1000: 'Normal', 0x2000: 'Cine'}

def gamepad_thread():
    """Pushes stick state to virtual gamepad at ~100Hz, independent of serial reads."""
    while True:
        gamepad.left_joystick(st_lh, st_lv)
        gamepad.right_joystick(st_rh, st_rv)
        # Camera wheel
        if camera > CAMERA_SENSITIVITY:
            gamepad.release_button(CAMERA_DOWN_BUTTON)
            gamepad.press_button(CAMERA_UP_BUTTON)
        elif camera < -CAMERA_SENSITIVITY:
            gamepad.release_button(CAMERA_UP_BUTTON)
            gamepad.press_button(CAMERA_DOWN_BUTTON)
        else:
            gamepad.release_button(CAMERA_UP_BUTTON)
            gamepad.release_button(CAMERA_DOWN_BUTTON)
        # Physical RC buttons (strip mode bits so buttons work in all modes)
        bits = rc_button_bits
        btn_bits = bits & ~0x3000
        for mask, vg_btn, _ in RC_BUTTONS:
            if btn_bits & mask == mask:
                gamepad.press_button(vg_btn)
            else:
                gamepad.release_button(vg_btn)
        # Flight mode switch (3-state via 0x3000 mask)
        mode_bits = bits & 0x3000
        if MODE_SPORT_BUTTON:
            if mode_bits == 0x0000:  # Sport
                gamepad.press_button(MODE_SPORT_BUTTON)
            else:
                gamepad.release_button(MODE_SPORT_BUTTON)
        if MODE_CINE_BUTTON:
            if mode_bits == 0x2000:  # Cine
                gamepad.press_button(MODE_CINE_BUTTON)
            else:
                gamepad.release_button(MODE_CINE_BUTTON)
        gamepad.update()
        time.sleep(0.01)

thread = Thread(target=gamepad_thread, daemon=True)
thread.start()

serial_buf = bytearray()

def read_duml_packet(s):
    """Read one DUML packet from serial buffer. Returns bytearray or empty on timeout."""
    global serial_buf
    # Bulk-read all available bytes into internal buffer
    waiting = s.in_waiting
    if waiting > 0:
        serial_buf.extend(s.read(waiting))
    elif len(serial_buf) == 0:
        # Nothing buffered, do a blocking read (uses serial timeout)
        chunk = s.read(1)
        if len(chunk) == 0:
            return bytearray()
        serial_buf.extend(chunk)
        # Grab anything else that arrived
        if s.in_waiting > 0:
            serial_buf.extend(s.read(s.in_waiting))

    # Find 0x55 sync byte in buffer
    while True:
        idx = serial_buf.find(0x55)
        if idx == -1:
            serial_buf.clear()
            return bytearray()
        if idx > 0:
            del serial_buf[:idx]

        # Need at least 3 bytes for header
        if len(serial_buf) < 3:
            return bytearray()

        pl = (serial_buf[1] | (serial_buf[2] << 8)) & 0x3FF
        if pl < 5 or pl > 512:
            del serial_buf[0:1]
            continue

        if len(serial_buf) < pl:
            return bytearray()  # incomplete packet, wait for more

        packet = bytes(serial_buf[:pl])
        del serial_buf[:pl]
        return packet

# --- Performance tracking ---
stat_start_ns = time.time_ns()
stat_packets_read = 0
stat_measure_packets = 0
stat_polls_sent = 0
stat_prev_measure_ns = 0
stat_max_jitter_ns = 0
stat_jitter_sum_ns = 0
stat_jitter_buckets = [0, 0, 0, 0, 0]  # <2ms, 2-4ms, 4-7ms, 7-20ms, >20ms

try:
    while True:
        # Poll stick + camera data (cmd_id=0x01) and buttons (cmd_id=0x27)
        send_duml(s, 0x0a, 0x06, 0x40, 0x06, 0x01, bytearray.fromhex(''))
        send_duml(s, 0x0a, 0x06, 0x40, 0x06, 0x27, bytearray.fromhex(''))
        stat_polls_sent += 1

        # Read and process all available packets
        data = read_duml_packet(s)
        if len(data) == 0:
            time.sleep(0.05)
            continue

        while len(data) > 0:
            stat_packets_read += 1

            # cmd_id=0x01 response (38 bytes): sticks + camera wheel
            if len(data) == 38 and data[10] == 0x01:
                now_ns = time.time_ns()
                stat_measure_packets += 1

                # Jitter tracking
                if stat_prev_measure_ns > 0:
                    delta_ns = now_ns - stat_prev_measure_ns
                    stat_jitter_sum_ns += delta_ns
                    if delta_ns > stat_max_jitter_ns:
                        stat_max_jitter_ns = delta_ns
                    delta_ms = delta_ns / 1_000_000
                    if delta_ms <= 2:
                        stat_jitter_buckets[0] += 1
                    elif delta_ms <= 4:
                        stat_jitter_buckets[1] += 1
                    elif delta_ms <= 7:
                        stat_jitter_buckets[2] += 1
                    elif delta_ms <= 20:
                        stat_jitter_buckets[3] += 1
                    else:
                        stat_jitter_buckets[4] += 1
                stat_prev_measure_ns = now_ns

                st_rh = parseInput(int.from_bytes(data[13:15], 'little'))
                st_rv = parseInput(int.from_bytes(data[16:18], 'little'))
                st_lv = parseInput(int.from_bytes(data[19:21], 'little'))
                st_lh = parseInput(int.from_bytes(data[22:24], 'little'))
                camera = parseInput(int.from_bytes(data[25:27], 'little'))

                # Live debug output (~15Hz max)
                if SHOW_DEBUG:
                    now_dbg = time.time()
                    if now_dbg - debug_last_display >= 0.066:
                        debug_last_display = now_dbg
                        bits = rc_button_bits
                        btn_bits = bits & ~0x3000
                        active = [name for mask, name in [(0x0002, 'Fn'), (0x0004, 'Cam'), (0x0060, 'Photo'), (0x0080, 'RTH')] if btn_bits & mask == mask]
                        mode = MODE_NAMES.get(bits & 0x3000, '?')
                        btn_str = ','.join(active) if active else '-'
                        sys.stdout.write(f'\r\033[K  LH={st_lh:>6d}  LV={st_lv:>6d}  RH={st_rh:>6d}  RV={st_rv:>6d}  Cam={camera:>6d}  Btn=[{btn_str}]  Mode={mode}')
                        sys.stdout.flush()

            # cmd_id=0x27 response (58 bytes): physical buttons
            elif len(data) == 58 and data[10] == 0x27:
                rc_button_bits = int.from_bytes(data[28:30], 'big')

            data = read_duml_packet(s)

except serial.SerialException as e:
    print('\n\nCould not read/write:', e)
except KeyboardInterrupt:
    print('\n\nDetected keyboard interrupt.')
finally:
    stat_end_ns = time.time_ns()
    gamepad.reset()
    gamepad.update()
    if s is not None:
        s.close()

    # --- Print performance stats ---
    elapsed_s = (stat_end_ns - stat_start_ns) / 1e9
    if elapsed_s > 0 and stat_measure_packets > 1:
        intervals = stat_measure_packets - 1
        avg_ms = stat_jitter_sum_ns / intervals / 1e6
        max_ms = stat_max_jitter_ns / 1e6

        print('\n--- Session Statistics ---')
        print(f'  Duration:            {elapsed_s:.1f}s')
        print(f'  Polls sent:          {stat_polls_sent:,}  ({stat_polls_sent / elapsed_s:.1f}/s)')
        print(f'  Packets read:        {stat_packets_read:,}  ({stat_packets_read / elapsed_s:.1f}/s)')
        print(f'  Stick packets:       {stat_measure_packets:,}  ({stat_measure_packets / elapsed_s:.1f}/s)')
        print(f'  Avg interval:        {avg_ms:.2f} ms')
        print(f'  Max interval:        {max_ms:.2f} ms')
        print(f'  Jitter distribution:')
        labels = ['< 2 ms', '2-4 ms', '4-7 ms', '7-20 ms', '> 20 ms']
        for label, count in zip(labels, stat_jitter_buckets):
            pct = 100 * count / intervals
            print(f'    {label:>8s}: {count:>8,}  ({pct:5.1f}%)')
    elif elapsed_s > 0:
        print(f'\nRan for {elapsed_s:.1f}s but received {stat_measure_packets} stick packets.')

print('Stopped.')
