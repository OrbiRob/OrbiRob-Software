import time

import board
import busio
import digitalio
import socket
import numpy as np

from adafruit_rgb_display import ili9341
from PIL import Image, ImageDraw, ImageFont

import ui_shutdown
import ui_battery
import ui_wifi

import subprocess
import threading

import rclpy

from rclpy.qos import (
    QoSProfile,
    ReliabilityPolicy,
    DurabilityPolicy
)

from rclpy.executors import SingleThreadedExecutor

from std_msgs.msg import Float32MultiArray

# VERSION
APP_VERSION = "1.0.1"

# IP Address
IP_CHECK_INTERVAL = 2.0

last_ip_check = 0.0
displayed_ip_address = None

# ============================================================
# DISPLAY GEOMETRY
# ============================================================

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
DISPLAY_ROTATION = 90


# ============================================================
# SPI BUS
# ============================================================

spi = busio.SPI(
    board.SCLK,
    MOSI=board.MOSI,
    MISO=board.MISO
)


# ============================================================
# TFT CONTROL
# ============================================================

tft_cs = digitalio.DigitalInOut(board.CE0)

dc = digitalio.DigitalInOut(board.D25)

reset = digitalio.DigitalInOut(board.D24)


display = ili9341.ILI9341(
    spi,
    cs=tft_cs,
    dc=dc,
    rst=reset,
    rotation=DISPLAY_ROTATION,
    baudrate=8000000
)


# ============================================================
# TOUCH CONTROL
# ============================================================

touch_cs = digitalio.DigitalInOut(board.CE1)
touch_cs.direction = digitalio.Direction.OUTPUT
touch_cs.value = True


touch_irq = digitalio.DigitalInOut(board.D4)
touch_irq.direction = digitalio.Direction.INPUT
touch_irq.pull = digitalio.Pull.UP


# ============================================================
# TOUCH CALIBRATION
#
# These points were measured with display rotation = 90.
#
# Format:
# (raw_x, raw_y, screen_x, screen_y)
# ============================================================

calibration_points = [
    (3653, 565, 20, 20),       # top-left
    (3566, 3708, 299, 20),     # top-right
    (588, 347, 20, 219),       # bottom-left
    (528, 3683, 299, 219),     # bottom-right
    (2160, 2061, 160, 120),    # center
]


# ============================================================
# CALCULATE AFFINE TOUCH CALIBRATION
#
# screen_x = AX*raw_x + BX*raw_y + CX
# screen_y = AY*raw_x + BY*raw_y + CY
# ============================================================

def calculate_calibration(points):

    matrix_a = np.array(
        [
            [raw_x, raw_y, 1.0]
            for raw_x, raw_y, screen_x, screen_y in points
        ],
        dtype=float
    )

    screen_x_values = np.array(
        [
            screen_x
            for raw_x, raw_y, screen_x, screen_y in points
        ],
        dtype=float
    )

    screen_y_values = np.array(
        [
            screen_y
            for raw_x, raw_y, screen_x, screen_y in points
        ],
        dtype=float
    )

    coeff_x, _, _, _ = np.linalg.lstsq(
        matrix_a,
        screen_x_values,
        rcond=None
    )

    coeff_y, _, _, _ = np.linalg.lstsq(
        matrix_a,
        screen_y_values,
        rcond=None
    )

    return coeff_x, coeff_y


coeff_x, coeff_y = calculate_calibration(
    calibration_points
)

AX, BX, CX = coeff_x
AY, BY, CY = coeff_y


# ============================================================
# CONVERT RAW TOUCH TO SCREEN COORDINATES
# ============================================================

def calibrate_touch(raw_x, raw_y):

    screen_x = (
        AX * raw_x +
        BX * raw_y +
        CX
    )

    screen_y = (
        AY * raw_x +
        BY * raw_y +
        CY
    )

    screen_x = int(round(screen_x))
    screen_y = int(round(screen_y))

    screen_x = max(
        0,
        min(SCREEN_WIDTH - 1, screen_x)
    )

    screen_y = max(
        0,
        min(SCREEN_HEIGHT - 1, screen_y)
    )

    return screen_x, screen_y


# ============================================================
# XPT2046 LOW-LEVEL READ
# ============================================================

def read_touch_channel(command):

    tx = bytearray([
        command,
        0x00,
        0x00
    ])

    rx = bytearray(3)

    while not spi.try_lock():
        pass

    try:

        spi.configure(
            baudrate=500000,
            polarity=0,
            phase=0,
            bits=8
        )

        # Make sure TFT is deselected on shared SPI bus
        tft_cs.value = True

        touch_cs.value = False

        spi.write_readinto(
            tx,
            rx
        )

        touch_cs.value = True

    finally:

        spi.unlock()

    value = (
        ((rx[1] << 8) | rx[2])
        >> 3
    )

    return value


# ============================================================
# READ FILTERED TOUCH POSITION
# ============================================================

def read_touch(samples=15):

    raw_x_values = []
    raw_y_values = []

    for _ in range(samples):

        if touch_irq.value:
            break

        raw_x_values.append(
            read_touch_channel(0xD0)
        )

        raw_y_values.append(
            read_touch_channel(0x90)
        )

        time.sleep(0.003)

    if len(raw_x_values) < 5:
        return None

    raw_x_values.sort()
    raw_y_values.sort()

    # Remove two extreme samples from each end
    raw_x_values = raw_x_values[2:-2]
    raw_y_values = raw_y_values[2:-2]

    raw_x = (
        sum(raw_x_values)
        // len(raw_x_values)
    )

    raw_y = (
        sum(raw_y_values)
        // len(raw_y_values)
    )

    return calibrate_touch(
        raw_x,
        raw_y
    )


# ============================================================
# COLOURS
# ============================================================

BLACK = (0, 0, 0)

WHITE = (255, 255, 255)

DARK_BLUE = (15, 35, 60)

BLUE = (35, 90, 150)

GREEN = (30, 140, 70)

RED = (180, 40, 40)

GRAY = (100, 110, 120)

LIGHT_GRAY = (200, 205, 210)


# ============================================================
# FONTS
# ============================================================

FONT_PATH_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans.ttf"
)

FONT_PATH_BOLD = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans-Bold.ttf"
)


try:

    font_brand = ImageFont.truetype(
        FONT_PATH_BOLD,
        16
    )

    font_orbirob = ImageFont.truetype(
        FONT_PATH_BOLD,
        28
    )

    font_button = ImageFont.truetype(
        FONT_PATH_BOLD,
        16
    )

    font_message = ImageFont.truetype(
        FONT_PATH_REGULAR,
        16
    )

    font_small = ImageFont.truetype(
        FONT_PATH_REGULAR,
        13
    )

    font_ip = ImageFont.truetype(
	    FONT_PATH_BOLD,
	    16
	)

except Exception:

    font_brand = ImageFont.load_default()
    font_orbirob = ImageFont.load_default()
    font_button = ImageFont.load_default()
    font_message = ImageFont.load_default()
    font_small = ImageFont.load_default()
    font_ip = ImageFont.load_default()


# ============================================================
# BUTTON GEOMETRY
#
#       BATTERY       WIFI
#
#            SHUTDOWN
# ============================================================

BUTTON_WIDTH = 125
BUTTON_HEIGHT = 45

LEFT_COLUMN_X = 25
RIGHT_COLUMN_X = 170

ROW_1_Y = 82
ROW_2_Y = 137


BATTERY_BOX = (
    LEFT_COLUMN_X,
    ROW_1_Y,
    LEFT_COLUMN_X + BUTTON_WIDTH,
    ROW_1_Y + BUTTON_HEIGHT
)


WIFI_BOX = (
    RIGHT_COLUMN_X,
    ROW_1_Y,
    RIGHT_COLUMN_X + BUTTON_WIDTH,
    ROW_1_Y + BUTTON_HEIGHT
)


SHUTDOWN_BOX = (
    97,
    ROW_2_Y,
    222,
    ROW_2_Y + BUTTON_HEIGHT
)


# ============================================================
# GENERIC DRAWING FUNCTIONS
# ============================================================

def draw_centered_text(
    draw,
    box,
    text,
    font,
    fill
):

    left, top, right, bottom = box

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (
        left +
        (right - left - text_width) // 2
    )

    y = (
        top +
        (bottom - top - text_height) // 2
        - 2
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill
    )


def draw_button(
    draw,
    box,
    text,
    colour
):

    draw.rounded_rectangle(
        box,
        radius=8,
        fill=colour,
        outline=WHITE,
        width=2
    )

    draw_centered_text(
        draw,
        box,
        text,
        font_button,
        WHITE
    )


def point_in_box(
    x,
    y,
    box
):

    left, top, right, bottom = box

    return (
        left <= x <= right
        and
        top <= y <= bottom
    )


# ============================================================
# BOOT / STARTUP SCREEN
# ============================================================

def show_boot_message(
    message,
    submessage="",
    step=0,
    total_steps=0
):

    image = Image.new(
        "RGB",
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        DARK_BLUE
    )

    draw = ImageDraw.Draw(image)

    # SONAROBOTICS

    brand_text = "SONAROBOTICS"

    brand_bbox = draw.textbbox(
        (0, 0),
        brand_text,
        font=font_brand
    )

    brand_width = (
        brand_bbox[2] -
        brand_bbox[0]
    )

    draw.text(
        (
            (SCREEN_WIDTH - brand_width) // 2,
            8
        ),
        brand_text,
        font=font_brand,
        fill=LIGHT_GRAY
    )

    # OrbiRob

    orbirob_text = "OrbiRob"

    orbirob_bbox = draw.textbbox(
        (0, 0),
        orbirob_text,
        font=font_orbirob
    )

    orbirob_width = (
        orbirob_bbox[2] -
        orbirob_bbox[0]
    )

    draw.text(
        (
            (SCREEN_WIDTH - orbirob_width) // 2,
            30
        ),
        orbirob_text,
        font=font_orbirob,
        fill=WHITE
    )

    draw.line(
        (20, 75, 300, 75),
        fill=GRAY,
        width=1
    )

    draw.text(
        (20, 105),
        message,
        font=font_message,
        fill=WHITE
    )

    if submessage:

        draw.text(
            (20, 138),
            submessage,
            font=font_small,
            fill=LIGHT_GRAY
        )

    # Progress bar

    if total_steps > 0:

        progress = max(
            0.0,
            min(
                1.0,
                step / total_steps
            )
        )

        bar_left = 20
        bar_top = 190
        bar_right = 300
        bar_bottom = 205

        draw.rectangle(
            (
                bar_left,
                bar_top,
                bar_right,
                bar_bottom
            ),
            outline=GRAY,
            width=1
        )

        fill_width = int(
            (bar_right - bar_left - 2)
            * progress
        )

        if fill_width > 0:

            draw.rectangle(
                (
                    bar_left + 1,
                    bar_top + 1,
                    bar_left + 1 + fill_width,
                    bar_bottom - 1
                ),
                fill=GREEN
            )

    display.image(image)


# ============================================================
# BATTERY MONITOR
# ============================================================

BATTERY_TOPIC = "/pico/proximity/distances_mm"

BATTERY_VOLTAGE_INDEX = 7
BATTERY_PERCENTAGE_INDEX = 8

LOW_BATTERY_PERCENTAGE = 5.0

# Battery must stay <= 5% for this long before shutdown.
LOW_BATTERY_CONFIRM_SECONDS = 5.0


battery_voltage = None
battery_percentage = None

low_battery_since = None
low_battery_shutdown_started = False

battery_monitor_node = None
battery_executor = None
battery_thread = None


def battery_monitor_callback(msg):

    global battery_voltage
    global battery_percentage
    global low_battery_since
    global low_battery_shutdown_started

    if len(msg.data) < 9:
        return

    try:
        voltage = float(
            msg.data[BATTERY_VOLTAGE_INDEX]
        )

        percentage = float(
            msg.data[BATTERY_PERCENTAGE_INDEX]
        )

    except (TypeError, ValueError):
        return

    # Reject obviously invalid data.
    if voltage <= 0.0:
        return

    if percentage < 0.0 or percentage > 100.0:
        return

    battery_voltage = voltage
    battery_percentage = percentage

    now = time.monotonic()

    if percentage <= LOW_BATTERY_PERCENTAGE:

        if low_battery_since is None:

            low_battery_since = now

            print(
                f"LOW BATTERY: {percentage:.0f}% "
                f"({voltage:.2f} V)"
            )

        elif (
            not low_battery_shutdown_started
            and
            now - low_battery_since
            >= LOW_BATTERY_CONFIRM_SECONDS
        ):

            low_battery_shutdown_started = True

            print(
                f"CRITICAL BATTERY: "
                f"{percentage:.0f}% "
                f"({voltage:.2f} V)"
            )

            print(
                "Automatic poweroff requested."
            )

            try:

                subprocess.Popen(
                    [
                        "sudo",
                        "-n",
                        "/usr/bin/systemctl",
                        "poweroff"
                    ]
                )

            except Exception as exc:

                print(
                    f"Automatic shutdown failed: {exc}"
                )

                # Allow another attempt.
                low_battery_shutdown_started = False

    else:

        # Battery recovered above threshold.
        low_battery_since = None


def start_battery_monitor():

    global battery_monitor_node
    global battery_executor
    global battery_thread

    if not rclpy.ok():
        rclpy.init(args=None)

    battery_monitor_node = rclpy.create_node(
        "orbirob_tft_battery_monitor"
    )

    qos = QoSProfile(depth=10)

    qos.reliability = (
        ReliabilityPolicy.BEST_EFFORT
    )

    qos.durability = (
        DurabilityPolicy.VOLATILE
    )

    battery_monitor_node.create_subscription(
        Float32MultiArray,
        BATTERY_TOPIC,
        battery_monitor_callback,
        qos
    )

    battery_executor = SingleThreadedExecutor()

    battery_executor.add_node(
        battery_monitor_node
    )

    battery_thread = threading.Thread(
        target=battery_executor.spin,
        daemon=True
    )

    battery_thread.start()

    print(
        "Battery monitor started: "
        f"shutdown at <= {LOW_BATTERY_PERCENTAGE:.0f}%"
    )
    
def get_ip_address():

    # Prefer OrbiRob's Wi-Fi interface.
    try:

        result = subprocess.run(
            [
                "/usr/sbin/ip",
                "-4",
                "-o",
                "addr",
                "show",
                "dev",
                "wlan0",
                "scope",
                "global"
            ],
            capture_output=True,
            text=True,
            timeout=1
        )

        for line in result.stdout.splitlines():

            fields = line.split()

            if len(fields) >= 4:

                address = fields[3].split("/")[0]

                if address:
                    return address

    except Exception:
        pass

    # Fallback: find the source address of the default route.
    try:

        result = subprocess.run(
            [
                "/usr/sbin/ip",
                "-4",
                "route",
                "get",
                "1.1.1.1"
            ],
            capture_output=True,
            text=True,
            timeout=1
        )

        fields = result.stdout.split()

        if "src" in fields:

            index = fields.index("src")

            if index + 1 < len(fields):
                return fields[index + 1]

    except Exception:
        pass

    return "No network"
    
        
    
# ============================================================
# MAIN MENU
# ============================================================

def show_main_menu():

    global displayed_ip_address
    
    image = Image.new(
        "RGB",
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        DARK_BLUE
    )

    draw = ImageDraw.Draw(image)

    # SONAROBOTICS

    brand_text = "SONAROBOTICS"

    brand_bbox = draw.textbbox(
        (0, 0),
        brand_text,
        font=font_brand
    )

    brand_width = (
        brand_bbox[2] -
        brand_bbox[0]
    )

    draw.text(
        (
            (SCREEN_WIDTH - brand_width) // 2,
            4
        ),
        brand_text,
        font=font_brand,
        fill=LIGHT_GRAY
    )

    # OrbiRob

    orbirob_text = "OrbiRob"

    orbirob_bbox = draw.textbbox(
        (0, 0),
        orbirob_text,
        font=font_orbirob
    )

    orbirob_width = (
        orbirob_bbox[2] -
        orbirob_bbox[0]
    )

    draw.text(
        (
            (SCREEN_WIDTH - orbirob_width) // 2,
            25
        ),
        orbirob_text,
        font=font_orbirob,
        fill=WHITE
    )

    draw.line(
        (20, 68, 300, 68),
        fill=GRAY,
        width=1
    )

    draw_button(
        draw,
        BATTERY_BOX,
        "BATTERY",
        GREEN
    )

    draw_button(
        draw,
        WIFI_BOX,
        "WIFI",
        BLUE
    )

    draw_button(
        draw,
        SHUTDOWN_BOX,
        "SHUTDOWN",
        RED
    )

    # --------------------------------------------------------
    # IP ADDRESS
    # --------------------------------------------------------

    hostname = socket.gethostname()
    ip_address = get_ip_address()
    displayed_ip_address = ip_address

    ip_text = f"{hostname} {ip_address}"

    ip_bbox = draw.textbbox(
        (0, 0),
        ip_text,
        font=font_ip
    )

    ip_width = (
        ip_bbox[2] -
        ip_bbox[0]
    )

    draw.text(
        (
            5, #  (SCREEN_WIDTH - ip_width) // 2,
            208
        ),
        ip_text,
        font=font_ip,
        fill=LIGHT_GRAY
    )

    version_text = f"v{APP_VERSION}"

    draw.text(
        (315, 10),
        version_text,
        font=font_small,
        fill="white",
        anchor="rb"
    )

    display.image(image)


# ============================================================
# GENERIC MESSAGE SCREEN
# ============================================================

def show_message(
    title,
    message,
    colour=BLUE
):

    image = Image.new(
        "RGB",
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        DARK_BLUE
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (15, 12),
        title,
        font=font_orbirob,
        fill=WHITE
    )

    message_box = (
        20,
        75,
        300,
        175
    )

    draw.rounded_rectangle(
        message_box,
        radius=10,
        fill=colour
    )

    draw_centered_text(
        draw,
        message_box,
        message,
        font_message,
        WHITE
    )

    display.image(image)


# ============================================================
# BUTTON DETECTION
# ============================================================

def button_at(
    x,
    y
):

    if point_in_box(
        x,
        y,
        BATTERY_BOX
    ):

        return "BATTERY"

    if point_in_box(
        x,
        y,
        WIFI_BOX
    ):

        return "WIFI"

    if point_in_box(
        x,
        y,
        SHUTDOWN_BOX
    ):

        return "SHUTDOWN"

    return None


# ============================================================
# SHARED UI OBJECT
#
# Passed to the individual menu modules.
# This prevents those modules from re-opening the TFT,
# touchscreen or GPIO resources.
# ============================================================

ui = {
    "display": display,

    "read_touch": read_touch,
    "touch_irq": touch_irq,

    "draw_button": draw_button,
    "draw_centered_text": draw_centered_text,
    "point_in_box": point_in_box,

    "font_brand": font_brand,
    "font_orbirob": font_orbirob,
    "font_button": font_button,
    "font_message": font_message,
    "font_small": font_small,

    "screen_width": SCREEN_WIDTH,
    "screen_height": SCREEN_HEIGHT,

    "colors": {
        "background": DARK_BLUE,
        "black": BLACK,
        "white": WHITE,
        "green": GREEN,
        "red": RED,
        "blue": BLUE,
        "gray": GRAY,
        "light_gray": LIGHT_GRAY,
    },
}


# ============================================================
# STARTUP INFORMATION
# ============================================================

print()

print(
    "SONAROBOTICS - OrbiRob"
)

print(
    "TFT UI starting..."
)

print()

print(
    "Touch calibration coefficients:"
)

print(
    f"AX={AX:.8f} "
    f"BX={BX:.8f} "
    f"CX={CX:.8f}"
)

print(
    f"AY={AY:.8f} "
    f"BY={BY:.8f} "
    f"CY={CY:.8f}"
)

print()

start_battery_monitor()

# ============================================================
# BOOT SCREEN SEQUENCE
# ============================================================

show_boot_message(
    "Starting OrbiRob...",
    "Initializing TFT interface",
    1,
    5
)

time.sleep(0.4)


show_boot_message(
    "Display ready",
    "Initializing touchscreen",
    2,
    5
)

time.sleep(0.4)


show_boot_message(
    "Touchscreen ready",
    "Starting robot services",
    3,
    5
)

time.sleep(0.4)


show_boot_message(
    "Checking system...",
    "Preparing OrbiRob",
    4,
    5
)

time.sleep(0.4)


show_boot_message(
    "System ready",
    "",
    5,
    5
)

time.sleep(0.5)


show_main_menu()


# ============================================================
# MAIN EVENT LOOP
# ============================================================

try:

    while True:
        # ----------------------------------------------------
        # CHECK FOR IP ADDRESS CHANGE
        # ----------------------------------------------------

        now = time.monotonic()

        if now - last_ip_check >= IP_CHECK_INTERVAL:

            last_ip_check = now

            current_ip = get_ip_address()

            if current_ip != displayed_ip_address:

                print(
                    f"IP address changed: "
                    f"{displayed_ip_address} -> {current_ip}"
                )

                show_main_menu()        

        # XPT2046 IRQ is active LOW
        if not touch_irq.value:

            touch_position = read_touch()

            if touch_position is not None:

                x, y = touch_position

                print(
                    f"Touch: X={x:3d} Y={y:3d}"
                )

                selected_button = button_at(
                    x,
                    y
                )

                # ------------------------------------------------
                # BATTERY
                # ------------------------------------------------

                if selected_button == "BATTERY":

                    print("BATTERY pressed")

                    ui_battery.run(ui)

                    show_main_menu()


                # ------------------------------------------------
                # WIFI
                # ------------------------------------------------

                elif selected_button == "WIFI":

                    print("WIFI pressed")

                    ui_wifi.run(ui)

                    show_main_menu()


                # ------------------------------------------------
                # SHUTDOWN
                # ------------------------------------------------

                elif selected_button == "SHUTDOWN":

                    print("SHUTDOWN pressed")

                    shutting_down = ui_shutdown.run(ui)

                    # If CANCEL was selected,
                    # ui_shutdown.run() returns here.

                    if not shutting_down:
                        show_main_menu()


            # Wait until finger/stylus is released
            while not touch_irq.value:

                time.sleep(0.01)


        time.sleep(0.02)


except KeyboardInterrupt:

    print()

    print(
        "OrbiRob TFT UI stopped."
    )


finally:

    try:
        if battery_executor is not None:
            battery_executor.shutdown()
    except Exception:
        pass

    try:
        if battery_monitor_node is not None:
            battery_monitor_node.destroy_node()
    except Exception:
        pass

    try:
        if rclpy.ok():
            rclpy.shutdown()
    except Exception:
        pass
        
    # Put chip-selects in inactive state

    try:
        touch_cs.value = True
    except Exception:
        pass

    try:
        tft_cs.value = True
    except Exception:
        pass


    # Release GPIO resources

    try:
        touch_cs.deinit()
    except Exception:
        pass

    try:
        tft_cs.deinit()
    except Exception:
        pass

    try:
        touch_irq.deinit()
    except Exception:
        pass

    try:
        dc.deinit()
    except Exception:
        pass

    try:
        reset.deinit()
    except Exception:
        pass
