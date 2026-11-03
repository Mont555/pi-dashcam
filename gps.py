import threading
import time
 
import pynmea2
import serial
from serial.tools import list_ports
 
UBLOX_VENDOR_ID = 0x1546
KNOTS_TO_MPH = 1.15078
STALE_SECONDS = 3
 
 
def find_usb_gps():
    for port in list_ports.comports():
        if port.vid == UBLOX_VENDOR_ID or "gps" in (port.description or "").lower():
            return port.device
    return None
 
 
class GPS:
    def __init__(self):
        self.fix = None
        threading.Thread(target=self._run, daemon=True).start()
 
    def reading(self):
        fix = self.fix
        if fix is None or time.monotonic() - fix[3] > STALE_SECONDS:
            return None
        return fix[:3]
 
    def status_text(self):
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
                with serial.Serial(port, timeout=2) as ser:
                    while True:
                        self.handle_line(ser.readline())
            except Exception as e:
                print(f"GPS: {e} - retrying in 2s")
                time.sleep(2)
 
    def handle_line(self, line):
        if line[3:6] != b"RMC":
            return
        try:
            msg = pynmea2.parse(line.decode("ascii", errors="ignore").strip())
        except pynmea2.ParseError:
            return
        if msg.status == "A":
            mph = (msg.spd_over_grnd or 0) * KNOTS_TO_MPH
            self.fix = (msg.latitude, msg.longitude, mph, time.monotonic())