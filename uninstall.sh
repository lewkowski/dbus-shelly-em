#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)

# Kill the service process if it exists
pids=$(pgrep -f "python $SCRIPT_DIR/dbus-shelly-em-smartmeter.py" || true)
if [ -n "$pids" ]; then
    kill $pids
fi

# Remove the symlink
rm -f /service/$SERVICE_NAME

# Remove install script from rc.local
filename=/data/rc.local
if [ -f $filename ]; then
    sed -i "\|$SCRIPT_DIR/install.sh|d" $filename
fi
