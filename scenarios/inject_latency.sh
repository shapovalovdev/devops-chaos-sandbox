#!/usr/bin/env bash
# Network latency failure injection scenario
# Resolves #4.

echo "--- Injecting network latency scenario ---"

INTERFACE="lo"
LATENCY="1500ms"

# Ensure tc is installed
if ! command -v tc &> /dev/null; then
  echo "ERROR: iproute2/tc command not found on host."
  exit 1
fi

# Check if there is already a root qdisc configured on interface
if tc qdisc show dev "$INTERFACE" | grep -q "netem"; then
  echo "Latency already injected on $INTERFACE. Skipping."
  exit 0
fi

echo "Adding 1.5s netem delay to dev $INTERFACE..."
tc qdisc add dev "$INTERFACE" root netem delay "$LATENCY"

echo "Latency of $LATENCY successfully injected on $INTERFACE."
echo "Restore command: sudo tc qdisc del dev $INTERFACE root"
exit 0
