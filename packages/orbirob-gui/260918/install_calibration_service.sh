#!/usr/bin/env bash

set -e

# ============================================================
# OrbiRob calibration/configuration service installer
#
# 1. Normalizes old microros.service name to:
#       micro_ros_agent.service
#
# 2. Enables the micro-ROS agent at boot
#
# 3. Installs:
#       orbirob_drive_config_sender.service
#
#    which starts after micro_ros_agent.service
# ============================================================


# ------------------------------------------------------------
# Determine OrbiRob user
# ------------------------------------------------------------

if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
    ORBIROB_USER="${SUDO_USER}"
else
    ORBIROB_USER="${USER}"
fi

# If script itself was started as root, prefer standard
# OrbiRob account if it exists.
if [ "${ORBIROB_USER}" = "root" ] && id orbirob >/dev/null 2>&1; then
    ORBIROB_USER="orbirob"
fi


ORBIROB_HOME="$(
    getent passwd "${ORBIROB_USER}" |
    cut -d: -f6
)"


if [ -z "${ORBIROB_HOME}" ]; then
    echo "ERROR: Could not determine home directory."
    exit 1
fi


echo
echo "=============================================="
echo " OrbiRob calibration service installation"
echo "=============================================="
echo
echo "User: ${ORBIROB_USER}"
echo "Home: ${ORBIROB_HOME}"
echo


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

OLD_AGENT_SERVICE="/etc/systemd/system/microros.service"
NEW_AGENT_SERVICE="/etc/systemd/system/micro_ros_agent.service"

CALIBRATION_SERVICE="/etc/systemd/system/orbirob_drive_config_sender.service"

ROS_SETUP="/opt/ros/jazzy/setup.bash"

ORBIROB_SETUP="${ORBIROB_HOME}/ros2_ws/orbiRob/install/setup.bash"

CALIBRATION_FILE="${ORBIROB_HOME}/orbirob_calibration/calibration.yaml"


# ------------------------------------------------------------
# Check ROS installation
# ------------------------------------------------------------

if [ ! -f "${ROS_SETUP}" ]; then
    echo "ERROR:"
    echo "ROS 2 Jazzy setup file not found:"
    echo "  ${ROS_SETUP}"
    exit 1
fi


if [ ! -f "${ORBIROB_SETUP}" ]; then
    echo "ERROR:"
    echo "OrbiRob workspace has not been built:"
    echo "  ${ORBIROB_SETUP}"
    echo
    echo "Build the workspace first."
    exit 1
fi


# ------------------------------------------------------------
# Normalize old micro-ROS agent service name
# ------------------------------------------------------------

if [ -f "${OLD_AGENT_SERVICE}" ]; then

    echo "Old service found:"
    echo "  microros.service"
    echo

    echo "Disabling old service..."

    sudo systemctl disable --now microros.service \
        >/dev/null 2>&1 || true


    if [ -f "${NEW_AGENT_SERVICE}" ]; then

        echo "micro_ros_agent.service already exists."
        echo "Keeping the new service."

        BACKUP="${OLD_AGENT_SERVICE}.legacy"

        echo "Moving old service to:"
        echo "  ${BACKUP}"

        sudo mv \
            "${OLD_AGENT_SERVICE}" \
            "${BACKUP}"

    else

        echo "Renaming:"
        echo "  microros.service"
        echo "to:"
        echo "  micro_ros_agent.service"

        sudo mv \
            "${OLD_AGENT_SERVICE}" \
            "${NEW_AGENT_SERVICE}"

    fi

fi


# ------------------------------------------------------------
# Verify micro-ROS agent service
# ------------------------------------------------------------

if [ ! -f "${NEW_AGENT_SERVICE}" ]; then

    echo
    echo "ERROR:"
    echo "micro_ros_agent.service was not found."
    echo
    echo "Expected:"
    echo "  ${NEW_AGENT_SERVICE}"

    exit 1
fi


# ------------------------------------------------------------
# Install calibration/config sender service
# ------------------------------------------------------------

echo
echo "Installing OrbiRob drive configuration sender service..."


sudo tee "${CALIBRATION_SERVICE}" >/dev/null <<EOF
[Unit]
Description=OrbiRob Drive Calibration Configuration Sender
Requires=micro_ros_agent.service
After=micro_ros_agent.service

[Service]
Type=simple

User=${ORBIROB_USER}
Group=${ORBIROB_USER}

Environment=HOME=${ORBIROB_HOME}

ExecStart=/bin/bash -lc 'source ${ROS_SETUP} && source ${ORBIROB_SETUP} && exec ros2 run orbirob_calibration orbirob_drive_config_sender'

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF


# ------------------------------------------------------------
# Reload systemd
# ------------------------------------------------------------

echo
echo "Reloading systemd..."

sudo systemctl daemon-reload


# ------------------------------------------------------------
# Enable micro-ROS agent
# ------------------------------------------------------------

echo
echo "Enabling micro_ros_agent.service..."

sudo systemctl enable micro_ros_agent.service


# ------------------------------------------------------------
# Enable calibration sender
# ------------------------------------------------------------

echo "Enabling orbirob_drive_config_sender.service..."

sudo systemctl enable orbirob_drive_config_sender.service


# ------------------------------------------------------------
# Check calibration file
# ------------------------------------------------------------

# ------------------------------------------------------------
# Create default calibration configuration
# ------------------------------------------------------------

CALIBRATION_DIR="${ORBIROB_HOME}/orbirob_calibration"

echo
echo "Checking calibration configuration..."


if [ ! -d "${CALIBRATION_DIR}" ]; then

    echo "Creating calibration directory:"
    echo "  ${CALIBRATION_DIR}"

    sudo mkdir -p "${CALIBRATION_DIR}"

    sudo chown \
        "${ORBIROB_USER}:${ORBIROB_USER}" \
        "${CALIBRATION_DIR}"

fi


if [ ! -f "${CALIBRATION_FILE}" ]; then

    echo
    echo "Creating default calibration file:"
    echo "  ${CALIBRATION_FILE}"

    sudo tee "${CALIBRATION_FILE}" >/dev/null <<EOF
version: 1

# Nominal OrbiRob drive configuration
#
# Wheel radius:       0.040 m
# Encoder resolution: 5760 ticks/revolution
# Wheel distance:     0.289 m

encoder:
  ticks_per_revolution: 5760

drive:
  left_meters_per_tick: 0.0000436332313
  right_meters_per_tick: 0.0000436332313
  wheel_separation_m: 0.289

calibration:
  calibrated: true
EOF

    sudo chown \
        "${ORBIROB_USER}:${ORBIROB_USER}" \
        "${CALIBRATION_FILE}"

    sudo chmod 644 \
        "${CALIBRATION_FILE}"

    echo "Default calibration created."

else

    echo "Existing calibration file found:"
    echo "  ${CALIBRATION_FILE}"

    echo "Leaving existing calibration unchanged."

fi


# ------------------------------------------------------------
# Start services now
# ------------------------------------------------------------

echo
echo "Starting micro-ROS agent..."

sudo systemctl restart micro_ros_agent.service


echo "Starting drive configuration sender..."

sudo systemctl restart orbirob_drive_config_sender.service


# ------------------------------------------------------------
# Final status
# ------------------------------------------------------------

echo
echo "=============================================="
echo " Installation complete"
echo "=============================================="
echo

echo -n "micro_ros_agent.service: "
systemctl is-enabled micro_ros_agent.service

echo -n "orbirob_drive_config_sender.service: "
systemctl is-enabled orbirob_drive_config_sender.service

echo
echo "Check status with:"
echo
echo "  systemctl status micro_ros_agent.service"
echo "  systemctl status orbirob_drive_config_sender.service"
echo
