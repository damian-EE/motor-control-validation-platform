#!/usr/bin/env python3
"""
Written with Claude (Anthropic's AI assistant); run, tested and debugged on real hardware by Damian Delgado Ayon.

motor_logger.py - log data from the Arduino motor controller to a CSV file.

The Phase 3 firmware prints one line every 500 ms:

    time_ms,pwm,rpm,current_mA,voltage_V

and accepts a speed (-255..255) typed as a number followed by a newline.

Examples
--------
List serial ports:
    python motor_logger.py --list

Run an automatic PWM sweep (hold each level for 8 s) and save a CSV:
    python motor_logger.py --port COM3 --sweep 60,100,140,180,220,255,180,100,0 --hold 8

Just record whatever you type into the Arduino Serial Monitor for 60 s:
    python motor_logger.py --port COM3 --duration 60

Test the script without any hardware (synthetic motor, runs 10x faster):
    python motor_logger.py --simulate --sim-speed 10
"""

import argparse
import csv
import math
import random
import sys
import time
from datetime import datetime
from pathlib import Path

COLUMNS = ["time_ms", "pwm", "rpm", "current_mA", "voltage_V"]
DEFAULT_SWEEP = "60,100,140,180,220,255,180,100,0"


# --------------------------------------------------------------------------
# Simulated serial port (for testing the logger/plotter with no hardware)
# --------------------------------------------------------------------------
class FakeSerial:
    """Mimics the parts of pyserial.Serial that this script uses.

    The model is a crude first-order DC motor: steady-state speed rises
    roughly linearly with PWM (after a dead band), current rises with
    speed/load, and the supply sags slightly under current. It exists only
    to exercise the code - never present its output as real test data.
    """

    def __init__(self, speed=1.0, interval_s=0.5):
        self.speed = speed
        self.interval = interval_s
        self.pwm = 0
        self.rpm = 0.0
        self.t0 = time.monotonic()
        self.next_emit = 0.0
        self.pending = []
        self.is_open = True

    @property
    def in_waiting(self):
        self._advance()
        return len(self.pending)

    def _advance(self):
        now = (time.monotonic() - self.t0) * self.speed
        while self.next_emit <= now:
            self.next_emit += self.interval
            target = 0.0
            if abs(self.pwm) > 25:
                target = math.copysign((abs(self.pwm) - 25) * 0.55, self.pwm)
            self.rpm += (target - self.rpm) * 0.35  # first-order lag
            load = abs(self.rpm) / 130.0
            current = 80 + 650 * load + random.gauss(0, 12) if abs(self.pwm) > 0 else 8
            volts = 12.0 - 0.0006 * current + random.gauss(0, 0.02)
            rpm = self.rpm + random.gauss(0, 1.5)
            line = f"{int(self.next_emit * 1000)},{self.pwm},{rpm:.1f},{current:.1f},{volts:.2f}\n"
            self.pending.append(line.encode())

    def readline(self):
        # Sleep (scaled) until the next line is ready
        while not self.in_waiting:
            time.sleep(0.01)
        return self.pending.pop(0)

    def write(self, data):
        try:
            self.pwm = int(data.decode().strip())
        except ValueError:
            pass
        self.pending.append(f"Speed set to: {self.pwm}\n".encode())

    def reset_input_buffer(self):
        self.pending.clear()

    def close(self):
        self.is_open = False


# --------------------------------------------------------------------------
def list_ports():
    from serial.tools import list_ports as lp

    ports = list(lp.comports())
    if not ports:
        print("No serial ports found. Is the Arduino plugged in?")
    for p in ports:
        print(f"{p.device}\t{p.description}")


def parse_line(raw):
    """Return a list of 5 floats, or None if the line isn't a data row."""
    try:
        text = raw.decode("utf-8", errors="ignore").strip()
    except AttributeError:
        text = str(raw).strip()
    parts = text.split(",")
    if len(parts) != len(COLUMNS):
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def open_port(args):
    if args.simulate:
        print(f"[sim] Using a simulated motor ({args.sim_speed}x speed). Not real data!")
        return FakeSerial(speed=args.sim_speed)
    import serial  # imported late so --simulate works without pyserial hardware

    if not args.port:
        sys.exit("Give the serial port with --port (e.g. COM3 or /dev/ttyACM0). Use --list to see ports.")
    ser = serial.Serial(args.port, args.baud, timeout=1)
    time.sleep(2.0)  # the Uno resets when the port opens; wait for it to boot
    ser.reset_input_buffer()
    return ser


def main():
    ap = argparse.ArgumentParser(description="Log motor controller data to CSV.")
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    ap.add_argument("--port", help="serial port, e.g. COM3 or /dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--out", help="CSV path (default: test_results/run_<timestamp>.csv)")
    ap.add_argument("--sweep", nargs="?", const=DEFAULT_SWEEP,
                    help=f"comma-separated PWM levels to step through (default if bare flag: {DEFAULT_SWEEP})")
    ap.add_argument("--hold", type=float, default=8.0, help="seconds to hold each sweep level")
    ap.add_argument("--duration", type=float, help="seconds to log when not sweeping")
    ap.add_argument("--simulate", action="store_true", help="use a fake motor instead of hardware")
    ap.add_argument("--sim-speed", type=float, default=1.0, help="simulation speed multiplier")
    args = ap.parse_args()

    if args.list:
        list_ports()
        return

    levels = [int(x) for x in args.sweep.split(",")] if args.sweep else []
    for lv in levels:
        if not -255 <= lv <= 255:
            sys.exit(f"PWM level {lv} is outside -255..255")

    if args.out:
        out = Path(args.out)
    else:
        out = Path("test_results") / f"run_{datetime.now():%Y%m%d_%H%M%S}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    if levels:
        total = args.hold * len(levels)
    else:
        total = args.duration or 60.0
    speed = args.sim_speed if args.simulate else 1.0

    ser = open_port(args)
    print(f"Logging to {out} for about {total:.0f} s. Ctrl+C stops early (motor is stopped on exit).")

    rows = 0
    t_start = time.monotonic()
    level_idx = -1
    try:
        with open(out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            while True:
                elapsed = (time.monotonic() - t_start) * speed
                if elapsed >= total:
                    break

                # Step the sweep forward when it's time
                if levels:
                    want = min(int(elapsed // args.hold), len(levels) - 1)
                    if want != level_idx:
                        level_idx = want
                        ser.write(f"{levels[level_idx]}\n".encode())
                        print(f"  t={elapsed:5.1f}s  -> PWM {levels[level_idx]}")

                raw = ser.readline()
                if not raw:
                    continue
                row = parse_line(raw)
                if row is None:
                    text = raw.decode("utf-8", errors="ignore").strip()
                    if text:
                        print(f"  [arduino] {text}")
                    continue
                writer.writerow(row)
                f.flush()
                rows += 1
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        try:
            ser.write(b"0\n")  # always leave the motor stopped
            time.sleep(0.2)
        except Exception:
            pass
        ser.close()

    print(f"Saved {rows} rows to {out}")
    if rows == 0:
        print("No data rows were received. Check the port, baud rate (9600) and that the Phase 3 firmware is loaded.")


if __name__ == "__main__":
    main()
