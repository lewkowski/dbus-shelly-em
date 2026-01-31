#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Kill the process only if it exists
pids=$(pgrep -f "python $SCRIPT_DIR/dbus-shelly-em-smartmeter.py" || true)
if [ -n "$pids" ]; then
    kill $pids
fi

chmod a+x $SCRIPT_DIR/service/run
$SCRIPT_DIR/service/run
