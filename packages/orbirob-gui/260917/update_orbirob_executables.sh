#!/bin/bash

set -e

ARCHIVE="./orbirob_executables.tar.xz"
DESTINATION="$HOME/ros2_ws/orbiRob/install"
TEMP_DIR=$(mktemp -d /tmp/orbirob_install_XXXXXX)

cleanup()
{
    rm -rf "$TEMP_DIR"
}

trap cleanup EXIT

echo "========================================"
echo " Updating OrbiRob executables"
echo "========================================"
echo

if [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: $ARCHIVE not found in current directory."
    exit 1
fi

echo "Extracting $ARCHIVE..."
echo

tar -xf "$ARCHIVE" -C "$TEMP_DIR"

if [ ! -d "$TEMP_DIR/install" ]; then
    echo "ERROR: Archive does not contain install/ at the top level."
    exit 1
fi

echo "Extraction successful."
echo

echo "Replacing:"
echo "  $DESTINATION"
echo

rm -rf "$DESTINATION"

mkdir -p "$(dirname "$DESTINATION")"

cp -a "$TEMP_DIR/install" "$DESTINATION"

if [ ! -d "$DESTINATION" ]; then
    echo "ERROR: Failed to update $DESTINATION"
    exit 1
fi

echo
echo "Successfully updated orbiRob executables"
