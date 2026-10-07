# ui_battery.py

import time

import rclpy

from PIL import Image, ImageDraw
from std_msgs.msg import Float32MultiArray

from rclpy.qos import (
    QoSProfile,
    ReliabilityPolicy,
    DurabilityPolicy,
)


# ============================================================
# ROS TOPIC
# ============================================================

BATTERY_TOPIC = "/pico/proximity/distances_mm"

BATTERY_VOLTAGE_INDEX = 7
BATTERY_PERCENTAGE_INDEX = 8
EXPECTED_DATA_COUNT = 9


# ============================================================
# BATTERY SCREEN GEOMETRY
# ============================================================

BACK_BOX = (
    97,
    180,
    222,
    225
)


# ============================================================
# ROS QOS
# ============================================================

qos = QoSProfile(depth=10)

qos.reliability = (
    ReliabilityPolicy.BEST_EFFORT
)

qos.durability = (
    DurabilityPolicy.VOLATILE
)


# ============================================================
# BATTERY DATA
# ============================================================

battery_voltage = -1.0
battery_percentage = -1.0


# ============================================================
# ROS CALLBACK
# ============================================================

def _battery_callback(msg):

    global battery_voltage
    global battery_percentage

    if len(msg.data) < EXPECTED_DATA_COUNT:
        return

    battery_voltage = float(
        msg.data[BATTERY_VOLTAGE_INDEX]
    )

    battery_percentage = float(
        msg.data[BATTERY_PERCENTAGE_INDEX]
    )


# ============================================================
# DRAW BATTERY SCREEN
# ============================================================

def _draw_screen(ui):

    display = ui["display"]

    draw_button = ui["draw_button"]
    draw_centered_text = ui["draw_centered_text"]

    font_brand = ui["font_brand"]
    font_orbirob = ui["font_orbirob"]
    font_button = ui["font_button"]
    font_message = ui["font_message"]
    font_small = ui["font_small"]

    screen_width = ui["screen_width"]
    screen_height = ui["screen_height"]

    colors = ui["colors"]

    background = colors["background"]
    white = colors["white"]
    green = colors["green"]
    blue = colors["blue"]
    gray = colors["gray"]
    light_gray = colors["light_gray"]

    image = Image.new(
        "RGB",
        (screen_width, screen_height),
        background
    )

    draw = ImageDraw.Draw(image)


    # --------------------------------------------------------
    # SONAROBOTICS
    # --------------------------------------------------------

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
            (screen_width - brand_width) // 2,
            4
        ),
        brand_text,
        font=font_brand,
        fill=light_gray
    )


    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = "Battery Status"

    title_bbox = draw.textbbox(
        (0, 0),
        title,
        font=font_orbirob
    )

    title_width = (
        title_bbox[2] -
        title_bbox[0]
    )

    draw.text(
        (
            (screen_width - title_width) // 2,
            25
        ),
        title,
        font=font_orbirob,
        fill=white
    )

    draw.line(
        (20, 68, 300, 68),
        fill=gray,
        width=1
    )


    # --------------------------------------------------------
    # BATTERY DATA
    # --------------------------------------------------------

    if battery_voltage >= 0.0:

        voltage_text = (
            f"{battery_voltage:.2f} V"
        )

        percentage_text = (
            f"{battery_percentage:.0f} %"
        )

        voltage_box = (
            25,
            78,
            155,
            125
        )

        percentage_box = (
            165,
            78,
            295,
            125
        )

        draw.rounded_rectangle(
            voltage_box,
            radius=8,
            fill=blue,
            outline=white,
            width=2
        )

        draw.rounded_rectangle(
            percentage_box,
            radius=8,
            fill=green,
            outline=white,
            width=2
        )

        draw_centered_text(
            draw,
            voltage_box,
            voltage_text,
            font_message,
            white
        )

        draw_centered_text(
            draw,
            percentage_box,
            percentage_text,
            font_message,
            white
        )


        # Labels

        voltage_label_box = (
            25,
            128,
            155,
            150
        )

        percentage_label_box = (
            165,
            128,
            295,
            150
        )

        draw_centered_text(
            draw,
            voltage_label_box,
            "Voltage",
            font_small,
            light_gray
        )

        draw_centered_text(
            draw,
            percentage_label_box,
            "Remaining",
            font_small,
            light_gray
        )

    else:

        unavailable_box = (
            20,
            82,
            300,
            145
        )

        draw_centered_text(
            draw,
            unavailable_box,
            "Battery data unavailable",
            font_message,
            light_gray
        )


    # --------------------------------------------------------
    # BACK BUTTON
    # --------------------------------------------------------

    draw_button(
        draw,
        BACK_BOX,
        "BACK",
        blue
    )


    # --------------------------------------------------------
    # SEND IMAGE TO TFT
    # --------------------------------------------------------

    display.image(image)


# ============================================================
# RUN BATTERY SCREEN
# ============================================================

def run(ui):

    global battery_voltage
    global battery_percentage

    battery_voltage = -1.0
    battery_percentage = -1.0

    node = None
    subscription = None


    # --------------------------------------------------------
    # READ BATTERY DATA FROM ROS
    # --------------------------------------------------------

    try:

        if not rclpy.ok():

            rclpy.init(args=None)


        node = rclpy.create_node(
            "orbirob_battery_ui"
        )


        subscription = node.create_subscription(
            Float32MultiArray,
            BATTERY_TOPIC,
            _battery_callback,
            qos
        )


        start_time = time.monotonic()


        while True:

            rclpy.spin_once(
                node,
                timeout_sec=0.05
            )


            if battery_voltage >= 0.0:
                break


            # Do not block the UI indefinitely
            if (
                time.monotonic() -
                start_time
                > 2.0
            ):
                break


    except Exception as e:

        print(
            f"Battery ROS error: {e}"
        )


    finally:

        if node is not None:

            node.destroy_node()


    # --------------------------------------------------------
    # LOG RESULT
    # --------------------------------------------------------

    if battery_voltage >= 0.0:

        print(
            f"Battery: "
            f"{battery_voltage:.2f} V, "
            f"{battery_percentage:.0f}%"
        )

    else:

        print(
            "Battery data unavailable"
        )


    # --------------------------------------------------------
    # DRAW SCREEN
    # --------------------------------------------------------

    _draw_screen(ui)


    # --------------------------------------------------------
    # TOUCH HANDLING
    #
    # The BATTERY button that opened this page may still
    # be physically pressed. Wait for release before looking
    # for the BACK button.
    # --------------------------------------------------------

    touch_irq = ui["touch_irq"]
    read_touch = ui["read_touch"]
    point_in_box = ui["point_in_box"]


    while not touch_irq.value:

        time.sleep(0.01)


    # --------------------------------------------------------
    # WAIT FOR BACK
    # --------------------------------------------------------

    while True:

        if not touch_irq.value:

            touch_position = read_touch()


            if touch_position is not None:

                x, y = touch_position

                print(
                    f"Battery screen touch: "
                    f"X={x:3d} Y={y:3d}"
                )


                if point_in_box(
                    x,
                    y,
                    BACK_BOX
                ):

                    print(
                        "Battery BACK pressed"
                    )


                    # Wait for release before returning
                    while not touch_irq.value:

                        time.sleep(0.01)


                    return


            # Wait for release
            while not touch_irq.value:

                time.sleep(0.01)


        time.sleep(0.02)
