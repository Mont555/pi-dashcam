"""Reads a USB GPS dongle (e.g. u-blox 7) in the background and keeps the latest fix.

Run it on its own to check the dongle is working:  python3 gps.py
"""
import threading
import time

import pynmea2
import serial
from serial.tools import list_ports

import config

UBLOX_VENDOR_ID = 0x1546
CH340_VENDOR_ID = 0x1A86
KNOTS_TO_MPH = 1.15078
STALE_SECONDS = 3       # no valid fix for this long = GPS lost


def find_usb_gps():
    """Return the serial port of the GPS, e.g. '/dev/ttyUSB0', or None."""
    if config.GPS_PORT:
        return config.GPS_PORT
    for port in list_ports.comports():
        if (port.vid in (UBLOX_VENDOR_ID, CH340_VENDOR_ID)
                or "gps" in (port.description or "").lower()):
            return port.device
    return None

class GPS:
    def __init__(self):
        self.fix = None         # (lat, lon, speed_mph, time) of the last valid fix
        threading.Thread(target=self._run, daemon=True).start()

    def reading(self):
        """Return (lat, lon, speed_mph), or None if there's no current fix."""
        fix = self.fix
        if fix is None or time.monotonic() - fix[3] > STALE_SECONDS:
            return None
        return fix[:3]

    def status_text(self):
        """Short text for the status bar, e.g. '52 MPH 52.92250N 1.47460W'."""
        fix = self.reading()
        if fix is None:
            return "NO GPS"
        lat, lon, mph = fix
        return (f"{mph:.0f} MPH {abs(lat):.5f}{'N' if lat >= 0 else 'S'} "
                f"{abs(lon):.5f}{'E' if lon >= 0 else 'W'}")

    def _run(self):
        while True:
            port = find_usb_gps()
            if port is None:
                time.sleep(5)
                continue
            try:
                with serial.Serial(port, config.GPS_BAUD, timeout=2) as ser:
                    while True:
                        self.handle_line(ser.readline())
            except Exception as e:
                print(f"GPS: {e} - retrying in 2s")
                time.sleep(2)

    def handle_line(self, line):
        # Only RMC has what we need; skip the other ~9 sentences a second without parsing
        if line[3:6] != b"RMC":
            return
        try:
            msg = pynmea2.parse(line.decode("ascii", errors="ignore").strip())
        except pynmea2.ParseError:
            return
        if msg.status == "A":   # A = valid fix, V = no fix
            mph = (msg.spd_over_grnd or 0) * KNOTS_TO_MPH
            self.fix = (msg.latitude, msg.longitude, mph, time.monotonic())