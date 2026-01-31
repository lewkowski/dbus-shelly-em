#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Kill the service process if it exists
pids=$(pgrep -f "python $SCRIPT_DIR/dbus-shelly-em-smartmeter.py" || true)
if [ -n "$pids" ]; then
    echo "Killing existing process(es): $pids"
    kill -9 $pids
    sleep 1
fi

# Release any orphaned dBus names to avoid "Bus name already exists" errors
# This handles the case where the process died but dBus still holds the name
dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ReleaseName string:com.victronenergy.grid.http_100 2>/dev/null || true
dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ReleaseName string:com.victronenergy.battery.http_101 2>/dev/null || true
dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ReleaseName string:com.victronenergy.genset.http_102 2>/dev/null || true
dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ReleaseName string:com.victronenergy.pvinverter.http_103 2>/dev/null || true

sleep 1

# Make sure the service script is executable
chmod a+x $SCRIPT_DIR/service/run

# Start the service via the supervise system
$SCRIPT_DIR/service/run
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Kill the process only if it exists
pids=$(pgrep -f "python $SCRIPT_DIR/dbus-shelly-em-smartmeter.py" || true)
if [ -n "$pids" ]; then
    kill $pids
fi

chmod a+x $SCRIPT_DIR/service/run
$SCRIPT_DIR/service/run
