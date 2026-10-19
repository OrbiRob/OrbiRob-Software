import time
import subprocess

from PIL import Image, ImageDraw


# ============================================================
# NMCLI HELPERS
# ============================================================

def run_nmcli(args, timeout=15):

    try:

        result = subprocess.run(
            ["/usr/bin/nmcli"] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return (
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip()
        )

    except Exception as error:

        return (
            -1,
            "",
            str(error)
        )


def split_nmcli_line(line):

    # nmcli terse output escapes ":" as "\:"
    fields = []
    current = ""
    escaped = False

    for char in line:

        if escaped:

            current += char
            escaped = False

        elif char == "\\":

            escaped = True

        elif char == ":":

            fields.append(current)
            current = ""

        else:

            current += char

    fields.append(current)

    return fields


# ============================================================
# WIFI STATUS
# ============================================================

def get_wifi_status():

    code, output, error = run_nmcli(
        [
            "-t",
            "-f",
            "TYPE,STATE,CONNECTION",
            "device",
            "status"
        ]
    )

    if code != 0:

        return False, "", error

    for line in output.splitlines():

        fields = split_nmcli_line(line)

        if len(fields) < 3:
            continue

        device_type = fields[0]
        state = fields[1]
        connection = fields[2]

        if device_type == "wifi":

            connected = (
                state == "connected"
            )

            return (
                connected,
                connection,
                ""
            )

    return False, "", "No Wi-Fi device"


# ============================================================
# WIFI SCAN
# ============================================================

def scan_networks():

    # --------------------------------------------------------
    # Force a fresh scan
    # --------------------------------------------------------

    code, output, error = run_nmcli(
        [
            "device",
            "wifi",
            "rescan"
        ],
        timeout=15
    )

    print(
        "Wi-Fi rescan:",
        code,
        output,
        error
    )

    # Allow NetworkManager enough time to populate results
    time.sleep(2.5)

    # --------------------------------------------------------
    # Read full scan list
    # --------------------------------------------------------

    code, output, error = run_nmcli(
        [
            "-t",
            "-f",
            "IN-USE,SSID,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list"
        ],
        timeout=15
    )

    if code != 0:

        print(
            "Wi-Fi list failed:",
            error
        )

        return [], error

    print("Raw Wi-Fi list:")
    print(output)

    networks = {}

    for line in output.splitlines():

        fields = split_nmcli_line(line)

        if len(fields) < 4:
            continue

        in_use = fields[0].strip()
        ssid = fields[1].strip()
        signal_text = fields[2].strip()
        security = fields[3].strip()

        if not ssid:
            continue

        try:

            signal = int(signal_text)

        except ValueError:

            signal = 0

        network = {
            "ssid": ssid,
            "signal": signal,
            "security": security,
            "active": in_use == "*"
        }

        # Multiple APs may have the same SSID.
        # Keep the strongest one.
        if (
            ssid not in networks
            or
            signal > networks[ssid]["signal"]
        ):

            networks[ssid] = network

    result = list(
        networks.values()
    )

    # Current network first, then strongest signal
    result.sort(
        key=lambda item: (
            not item["active"],
            -item["signal"]
        )
    )

    print(
        "Networks found:",
        [
            (
                network["ssid"],
                network["signal"]
            )
            for network in result
        ]
    )

    return result, ""


# ============================================================
# CONNECT TO NETWORK
# ============================================================

def connect_network(
    ssid,
    password=None
):

    args = [
        "device",
        "wifi",
        "connect",
        ssid
    ]

    if password:

        args += [
            "password",
            password
        ]

    return run_nmcli(
        args,
        timeout=30
    )


# ============================================================
# BASIC SCREEN HELPERS
# ============================================================

def make_screen(ui):

    image = Image.new(
        "RGB",
        (
            ui["screen_width"],
            ui["screen_height"]
        ),
        ui["colors"]["background"]
    )

    draw = ImageDraw.Draw(image)

    return image, draw


def draw_title(
    ui,
    draw,
    title
):

    draw.text(
        (12, 5),
        title,
        font=ui["font_orbirob"],
        fill=ui["colors"]["white"]
    )

    draw.line(
        (12, 42, 308, 42),
        fill=ui["colors"]["gray"],
        width=1
    )


def wait_release(ui):

    while not ui["touch_irq"].value:

        time.sleep(0.01)


# ============================================================
# MAIN WIFI SCREEN
# ============================================================

def show_wifi_home(ui):

    connected, connection, error = (
        get_wifi_status()
    )

    image, draw = make_screen(ui)

    draw_title(
        ui,
        draw,
        "Wi-Fi"
    )

    if connected:

        draw.text(
            (18, 55),
            "Connected",
            font=ui["font_message"],
            fill=ui["colors"]["green"]
        )

        ssid = connection

        if len(ssid) > 28:

            ssid = (
                ssid[:25] +
                "..."
            )

        draw.text(
            (18, 80),
            ssid,
            font=ui["font_message"],
            fill=ui["colors"]["white"]
        )

    else:

        draw.text(
            (18, 55),
            "Not connected",
            font=ui["font_message"],
            fill=ui["colors"]["red"]
        )

        if error:

            text = error

            if len(text) > 34:

                text = (
                    text[:31] +
                    "..."
                )

            draw.text(
                (18, 80),
                text,
                font=ui["font_small"],
                fill=ui["colors"]["light_gray"]
            )

    scan_box = (
        20,
        120,
        145,
        168
    )

    back_box = (
        175,
        120,
        300,
        168
    )

    ui["draw_button"](
        draw,
        scan_box,
        "NETWORKS",
        ui["colors"]["blue"]
    )

    ui["draw_button"](
        draw,
        back_box,
        "BACK",
        ui["colors"]["gray"]
    )

    ui["display"].image(image)

    return scan_box, back_box


# ============================================================
# SCANNING SCREEN
# ============================================================

def show_scanning(ui):

    image, draw = make_screen(ui)

    draw_title(
        ui,
        draw,
        "Wi-Fi"
    )

    draw.text(
        (65, 100),
        "Scanning networks...",
        font=ui["font_message"],
        fill=ui["colors"]["white"]
    )

    ui["display"].image(image)


# ============================================================
# NETWORK LIST SCREEN
# ============================================================

def network_list_screen(
    ui,
    networks,
    page
):

    image, draw = make_screen(ui)

    draw_title(
        ui,
        draw,
        "Networks"
    )

    rows_per_page = 4

    start = (
        page *
        rows_per_page
    )

    visible = networks[
        start:start + rows_per_page
    ]

    network_boxes = []

    # Slightly higher because full 240 pixels are not visible
    y = 46

    for network in visible:

        box = (
            10,
            y,
            310,
            y + 31
        )

        colour = ui["colors"]["blue"]

        if network["active"]:

            colour = ui["colors"]["green"]

        draw.rounded_rectangle(
            box,
            radius=5,
            fill=colour,
            outline=ui["colors"]["white"],
            width=1
        )

        ssid = network["ssid"]

        if len(ssid) > 21:

            ssid = (
                ssid[:18] +
                "..."
            )

        draw.text(
            (16, y + 5),
            ssid,
            font=ui["font_message"],
            fill=ui["colors"]["white"]
        )

        security = network["security"]

        lock_text = ""

        if (
            security
            and
            security != "--"
        ):

            lock_text = "*"

        info = (
            f"{network['signal']:3d}% {lock_text}"
        )

        draw.text(
            (250, y + 7),
            info,
            font=ui["font_small"],
            fill=ui["colors"]["white"]
        )

        network_boxes.append(
            (
                box,
                network
            )
        )

        y += 34

    # Controls moved upward
    prev_box = (
        10,
        184,
        80,
        214
    )

    next_box = (
        85,
        184,
        155,
        214
    )

    refresh_box = (
        160,
        184,
        235,
        214
    )

    back_box = (
        240,
        184,
        310,
        214
    )

    ui["draw_button"](
        draw,
        prev_box,
        "<",
        ui["colors"]["gray"]
    )

    ui["draw_button"](
        draw,
        next_box,
        ">",
        ui["colors"]["gray"]
    )

    ui["draw_button"](
        draw,
        refresh_box,
        "SCAN",
        ui["colors"]["blue"]
    )

    ui["draw_button"](
        draw,
        back_box,
        "BACK",
        ui["colors"]["gray"]
    )

    ui["display"].image(image)

    return (
        network_boxes,
        prev_box,
        next_box,
        refresh_box,
        back_box
    )


# ============================================================
# NETWORK SELECTION LOOP
# ============================================================

def choose_network(ui):

    show_scanning(ui)

    networks, error = (
        scan_networks()
    )

    if not networks:

        show_message(
            ui,
            "Wi-Fi",
            "No networks found",
            error
        )

        return

    page = 0

    rows_per_page = 4

    max_page = max(
        0,
        (
            len(networks) - 1
        )
        // rows_per_page
    )

    while True:

        (
            network_boxes,
            prev_box,
            next_box,
            refresh_box,
            back_box
        ) = network_list_screen(
            ui,
            networks,
            page
        )

        while True:

            if not ui["touch_irq"].value:

                position = (
                    ui["read_touch"]()
                )

                if position is not None:

                    x, y = position

                    selected = None

                    # ----------------------------------------
                    # Network selection
                    # ----------------------------------------

                    for box, network in network_boxes:

                        if ui["point_in_box"](
                            x,
                            y,
                            box
                        ):

                            selected = network
                            break

                    if selected is not None:

                        wait_release(ui)

                        handle_network(
                            ui,
                            selected
                        )

                        return

                    # ----------------------------------------
                    # Previous page
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        prev_box
                    ):

                        if page > 0:

                            page -= 1

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Next page
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        next_box
                    ):

                        if page < max_page:

                            page += 1

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Rescan
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        refresh_box
                    ):

                        wait_release(ui)

                        show_scanning(ui)

                        networks, error = (
                            scan_networks()
                        )

                        page = 0

                        max_page = max(
                            0,
                            (
                                len(networks) - 1
                            )
                            // rows_per_page
                        )

                        break

                    # ----------------------------------------
                    # Back
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        back_box
                    ):

                        wait_release(ui)

                        return

                wait_release(ui)

            time.sleep(0.02)


# ============================================================
# HANDLE SELECTED NETWORK
# ============================================================

def handle_network(
    ui,
    network
):

    ssid = network["ssid"]
    security = network["security"]

    # --------------------------------------------------------
    # Already connected
    # --------------------------------------------------------

    if network["active"]:

        show_message(
            ui,
            "Wi-Fi",
            "Already connected",
            ssid
        )

        return

    # --------------------------------------------------------
    # First try WITHOUT supplying a password.
    #
    # If NetworkManager already has a saved connection/profile
    # for this SSID, it should reuse the stored credentials.
    # --------------------------------------------------------

    image, draw = make_screen(ui)

    draw_title(
        ui,
        draw,
        "Wi-Fi"
    )

    draw.text(
        (55, 85),
        "Connecting...",
        font=ui["font_message"],
        fill=ui["colors"]["white"]
    )

    draw.text(
        (45, 115),
        ssid[:28],
        font=ui["font_small"],
        fill=ui["colors"]["light_gray"]
    )

    ui["display"].image(image)

    code, output, error = (
        connect_network(
            ssid,
            None
        )
    )

    print("Saved Wi-Fi connection attempt:")
    print("SSID:", ssid)
    print("Return code:", code)
    print("stdout:", output)
    print("stderr:", error)

    # --------------------------------------------------------
    # Existing credentials worked
    # --------------------------------------------------------

    if code == 0:

        show_message(
            ui,
            "Wi-Fi",
            "Connected",
            ssid
        )

        return

    # --------------------------------------------------------
    # Open network - nothing more to ask
    # --------------------------------------------------------

    if (
        not security
        or
        security == "--"
    ):

        show_message(
            ui,
            "Connection Failed",
            "Unable to connect",
            error
        )

        return

    # --------------------------------------------------------
    # No usable saved password.
    # Ask the user for one.
    # --------------------------------------------------------

    password = keyboard(
        ui,
        ssid
    )

    if password is None:

        return

    do_connect(
        ui,
        ssid,
        password
    )


# ============================================================
# CONNECT
# ============================================================

def do_connect(
    ui,
    ssid,
    password
):

    image, draw = make_screen(ui)

    draw_title(
        ui,
        draw,
        "Wi-Fi"
    )

    draw.text(
        (65, 85),
        "Connecting...",
        font=ui["font_message"],
        fill=ui["colors"]["white"]
    )

    short_ssid = ssid

    if len(short_ssid) > 25:

        short_ssid = (
            short_ssid[:22] +
            "..."
        )

    draw.text(
        (45, 115),
        short_ssid,
        font=ui["font_small"],
        fill=ui["colors"]["light_gray"]
    )

    ui["display"].image(image)

    code, output, error = (
        connect_network(
            ssid,
            password
        )
    )

    # Do not log password
    print("Wi-Fi connection result:")
    print("SSID:", ssid)
    print("Return code:", code)
    print("stdout:", output)
    print("stderr:", error)

    if code == 0:

        show_message(
            ui,
            "Wi-Fi",
            "Connected",
            ssid
        )

    else:

        message = error

        if not message:

            message = output

        show_message(
            ui,
            "Connection Failed",
            "Unable to connect",
            message
        )


# ============================================================
# GENERIC MESSAGE SCREEN
# ============================================================

def show_message(
    ui,
    title,
    message,
    detail=""
):

    image, draw = make_screen(ui)

    draw_title(
        ui,
        draw,
        title
    )

    draw.text(
        (20, 70),
        message,
        font=ui["font_message"],
        fill=ui["colors"]["white"]
    )

    if detail:

        short_detail = detail

        if len(short_detail) > 40:

            short_detail = (
                short_detail[:37] +
                "..."
            )

        draw.text(
            (20, 100),
            short_detail,
            font=ui["font_small"],
            fill=ui["colors"]["light_gray"]
        )

    ok_box = (
        105,
        155,
        215,
        205
    )

    ui["draw_button"](
        draw,
        ok_box,
        "OK",
        ui["colors"]["gray"]
    )

    ui["display"].image(image)

    while True:

        if not ui["touch_irq"].value:

            position = (
                ui["read_touch"]()
            )

            if position is not None:

                x, y = position

                if ui["point_in_box"](
                    x,
                    y,
                    ok_box
                ):

                    wait_release(ui)

                    return

            wait_release(ui)

        time.sleep(0.02)


# ============================================================
# PASSWORD KEYBOARD
# ============================================================

KEYBOARD_PAGES = {

    "abc": [
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm"
    ],

    "ABC": [
        "QWERTYUIOP",
        "ASDFGHJKL",
        "ZXCVBNM"
    ],

    "123": [
        "1234567890",
        "-_=+@#$%&",
        ".,!?/:;()"
    ]
}


def keyboard(
    ui,
    ssid
):

    password = ""

    page_name = "abc"

    show_password = False

    while True:

        image, draw = make_screen(ui)

        # ----------------------------------------------------
        # SSID
        # ----------------------------------------------------

        ssid_text = ssid

        if len(ssid_text) > 23:

            ssid_text = (
                ssid_text[:20] +
                "..."
            )

        draw.text(
            (8, 3),
            ssid_text,
            font=ui["font_small"],
            fill=ui["colors"]["white"]
        )

        # ----------------------------------------------------
        # Password display
        # ----------------------------------------------------

        if show_password:

            password_text = (
                password[-28:]
            )

        else:

            password_text = (
                "*" *
                min(
                    len(password),
                    28
                )
            )

        draw.rectangle(
            (
                8,
                22,
                312,
                47
            ),
            outline=ui["colors"]["gray"],
            width=1
        )

        draw.text(
            (12, 27),
            password_text,
            font=ui["font_small"],
            fill=ui["colors"]["white"]
        )

        # ----------------------------------------------------
        # Character keys
        # ----------------------------------------------------

        key_boxes = []

        rows = KEYBOARD_PAGES[
            page_name
        ]

        row_y_values = [
            52,
            84,
            116
        ]

        for row_index, row in enumerate(rows):

            count = len(row)

            available_width = 304

            key_width = (
                available_width
                //
                max(
                    count,
                    1
                )
            )

            start_x = (
                8
                +
                (
                    available_width
                    -
                    key_width * count
                )
                // 2
            )

            y = row_y_values[
                row_index
            ]

            for index, character in enumerate(row):

                x = (
                    start_x
                    +
                    index * key_width
                )

                box = (
                    x,
                    y,
                    x + key_width - 2,
                    y + 27
                )

                draw.rounded_rectangle(
                    box,
                    radius=3,
                    fill=ui["colors"]["blue"],
                    outline=ui["colors"]["white"],
                    width=1
                )

                ui["draw_centered_text"](
                    draw,
                    box,
                    character,
                    ui["font_small"],
                    ui["colors"]["white"]
                )

                key_boxes.append(
                    (
                        box,
                        character
                    )
                )

        # ----------------------------------------------------
        # Control row
        # ----------------------------------------------------

        mode_box = (
            8,
            148,
            57,
            177
        )

        show_box = (
            62,
            148,
            122,
            177
        )

        space_box = (
            127,
            148,
            192,
            177
        )

        backspace_box = (
            197,
            148,
            252,
            177
        )

        clear_box = (
            257,
            148,
            312,
            177
        )

        cancel_box = (
            8,
            183,
            100,
            214
        )

        connect_box = (
            108,
            183,
            312,
            214
        )

        next_mode = {
            "abc": "ABC",
            "ABC": "123",
            "123": "abc"
        }[page_name]

        ui["draw_button"](
            draw,
            mode_box,
            next_mode,
            ui["colors"]["gray"]
        )

        ui["draw_button"](
            draw,
            show_box,
            (
                "HIDE"
                if show_password
                else "SHOW"
            ),
            ui["colors"]["gray"]
        )

        ui["draw_button"](
            draw,
            space_box,
            "SPACE",
            ui["colors"]["gray"]
        )

        ui["draw_button"](
            draw,
            backspace_box,
            "<-",
            ui["colors"]["gray"]
        )

        ui["draw_button"](
            draw,
            clear_box,
            "CLR",
            ui["colors"]["gray"]
        )

        ui["draw_button"](
            draw,
            cancel_box,
            "CANCEL",
            ui["colors"]["gray"]
        )

        ui["draw_button"](
            draw,
            connect_box,
            "CONNECT",
            ui["colors"]["green"]
        )

        ui["display"].image(image)

        # ----------------------------------------------------
        # Keyboard touch handling
        # ----------------------------------------------------

        while True:

            if not ui["touch_irq"].value:

                position = (
                    ui["read_touch"]()
                )

                if position is not None:

                    x, y = position

                    selected_character = None

                    # ----------------------------------------
                    # Character keys
                    # ----------------------------------------

                    for box, character in key_boxes:

                        if ui["point_in_box"](
                            x,
                            y,
                            box
                        ):

                            selected_character = (
                                character
                            )

                            break

                    if selected_character is not None:

                        password += (
                            selected_character
                        )

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # abc / ABC / 123
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        mode_box
                    ):

                        page_name = (
                            next_mode
                        )

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Show / hide password
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        show_box
                    ):

                        show_password = (
                            not show_password
                        )

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Space
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        space_box
                    ):

                        password += " "

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Backspace
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        backspace_box
                    ):

                        password = (
                            password[:-1]
                        )

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Clear
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        clear_box
                    ):

                        password = ""

                        wait_release(ui)

                        break

                    # ----------------------------------------
                    # Cancel
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        cancel_box
                    ):

                        wait_release(ui)

                        return None

                    # ----------------------------------------
                    # Connect
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        connect_box
                    ):

                        wait_release(ui)

                        return password

                wait_release(ui)

            time.sleep(0.02)


# ============================================================
# WIFI MENU ENTRY POINT
# ============================================================

def run(ui):

    print(
        "Wi-Fi screen opened"
    )

    while True:

        scan_box, back_box = (
            show_wifi_home(ui)
        )

        while True:

            if not ui["touch_irq"].value:

                position = (
                    ui["read_touch"]()
                )

                if position is not None:

                    x, y = position

                    # ----------------------------------------
                    # Networks
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        scan_box
                    ):

                        wait_release(ui)

                        choose_network(ui)

                        break

                    # ----------------------------------------
                    # Back
                    # ----------------------------------------

                    if ui["point_in_box"](
                        x,
                        y,
                        back_box
                    ):

                        wait_release(ui)

                        return

                wait_release(ui)

            time.sleep(0.02)
