#!/bin/bash

set -e

echo "***** Patch To fix the terminal coming up after 2 minutes"

systemctl --user mask --now pemmican-reset.service


