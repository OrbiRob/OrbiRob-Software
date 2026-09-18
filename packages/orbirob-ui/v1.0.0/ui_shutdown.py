import time
import subprocess
from PIL import Image, ImageDraw


def run(ui):

    display = ui["display"]
    read_touch = ui["read_touch"]
    touch_irq = ui["touch_irq"]
    draw_button = ui["draw_button"]
    point_in_box = ui["point_in_box"]

    SCREEN_WIDTH = ui["screen_width"]
    SCREEN_HEIGHT = ui["screen_height"]

    DARK_BLUE = ui["colors"]["background"]
    WHITE = ui["colors"]["white"]
    RED = ui["colors"]["red"]
    GRAY = ui["colors"]["gray"]

    font_orbirob = ui["font_orbirob"]
    font_message = ui["font_message"]

    image = Image.new(
        "RGB",
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        DARK_BLUE
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (15, 12),
        "Shutdown",
        font=font_orbirob,
        fill=WHITE
    )

    draw.text(
        (60, 65),
        "Power off OrbiRob?",
        font=font_message,
        fill=WHITE
    )

    yes_box = (
        25,
        115,
        145,
        170
    )

    cancel_box = (
        175,
        115,
        295,
        170
    )

    draw_button(
        draw,
        yes_box,
        "YES",
        RED
    )

    draw_button(
        draw,
        cancel_box,
        "CANCEL",
        GRAY
    )

    display.image(image)

    while True:

        if not touch_irq.value:

            touch_position = read_touch()

            if touch_position is not None:

                x, y = touch_position

                if point_in_box(
                    x,
                    y,
                    yes_box
                ):

                    show_shutdown_message(ui)

                    time.sleep(0.5)

                subprocess.Popen(
                    [
	                "sudo",
	                "-n",
	                "/usr/bin/systemctl",
	                "poweroff"
                    ]
                )

                return True

                if point_in_box(
                    x,
                    y,
                    cancel_box
                ):

                    return false

            while not touch_irq.value:
                time.sleep(0.01)

        time.sleep(0.02)


def show_shutdown_message(ui):

    image = Image.new(
        "RGB",
        (
            ui["screen_width"],
            ui["screen_height"]
        ),
        ui["colors"]["background"]
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (15, 12),
        "OrbiRob",
        font=ui["font_orbirob"],
        fill=ui["colors"]["white"]
    )

    draw.text(
        (65, 110),
        "Shutting Down...",
        font=ui["font_message"],
        fill=ui["colors"]["white"]
    )

    ui["display"].image(image)


def show_error(ui):

    image = Image.new(
        "RGB",
        (
            ui["screen_width"],
            ui["screen_height"]
        ),
        ui["colors"]["background"]
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (15, 12),
        "ERROR",
        font=ui["font_orbirob"],
        fill=ui["colors"]["white"]
    )

    draw.text(
        (70, 110),
        "Shutdown Failed",
        font=ui["font_message"],
        fill=ui["colors"]["white"]
    )

    ui["display"].image(image)
