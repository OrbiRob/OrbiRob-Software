#!/bin/bash

BOOTSEL_PROGRAM="./pico_bootsel"
UF2_FILE="./orbirob_pico.uf2"
MOUNT_POINT="/media/orbirob/RPI-RPI2"
WAIT_SECONDS=10

echo "========================================"
echo " OrbiRob Pico UF2 Flash"
echo "========================================"
echo

# ------------------------------------------------------------
# Check required files
# ------------------------------------------------------------

if [ ! -f "$BOOTSEL_PROGRAM" ]; then
    echo "ERROR: $BOOTSEL_PROGRAM not found in current directory."
    exit 1
fi

if [ ! -x "$BOOTSEL_PROGRAM" ]; then
    echo "ERROR: $BOOTSEL_PROGRAM is not executable."
    echo "Run:"
    echo "  chmod +x $BOOTSEL_PROGRAM"
    exit 1
fi

if [ ! -f "$UF2_FILE" ]; then
    echo "ERROR: $UF2_FILE not found in current directory."
    exit 1
fi


# ------------------------------------------------------------
# Put Pico into BOOTSEL mode
# ------------------------------------------------------------

echo "Putting Pico into BOOTSEL mode..."

"$BOOTSEL_PROGRAM"

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: pico_bootsel failed."
    exit 1
fi

echo "pico_bootsel executed successfully."
echo


# ------------------------------------------------------------
# Wait for RPI-RP2 USB drive
# ------------------------------------------------------------

echo "Waiting ${WAIT_SECONDS} seconds for Pico BOOTSEL drive..."
sleep "$WAIT_SECONDS"

echo
echo "Current block devices:"
echo "----------------------------------------"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS
echo "----------------------------------------"
echo


# ------------------------------------------------------------
# Check for RPI-RP2
# ------------------------------------------------------------

MOUNT_POINT=$(lsblk -nr -o LABEL,MOUNTPOINTS | \
    awk '$1 == "RPI-RP2" {print $2; exit}')
    
if [ -z "$MOUNT_POINT" ]; then
    echo "ERROR: RPI-RP2 was detected but is not mounted."
    echo
    lsblk -o NAME,LABEL,FSTYPE,MOUNTPOINTS
    exit 1
fi

echo "RPI-RP2 detected and mounted at:"
echo "  $MOUNT_POINT"


# ------------------------------------------------------------
# Check mount point
# ------------------------------------------------------------

if [ ! -d "$MOUNT_POINT" ]; then
    echo
    echo "ERROR: RPI-RP2 was detected, but mount point does not exist:"
    echo "  $MOUNT_POINT"
    echo
    echo "The USB drive may not have been automatically mounted."
    exit 1
fi

if ! mountpoint -q "$MOUNT_POINT"; then
    echo
    echo "ERROR: $MOUNT_POINT exists but is not a mounted filesystem."
    exit 1
fi

echo "RPI-RP2 mounted at:"
echo "  $MOUNT_POINT"
echo


# ------------------------------------------------------------
# Copy UF2
# ------------------------------------------------------------

echo "Copying:"
echo "  $UF2_FILE"
echo "to:"
echo "  $MOUNT_POINT/"
echo

cp -v "$UF2_FILE" "$MOUNT_POINT/"

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Failed to flash UF2 file."
    exit 1
fi

sync

echo
echo "========================================"
echo " SUCCESS"
echo " orbirob_pico.uf2 flashed to Pico."
echo "========================================"
