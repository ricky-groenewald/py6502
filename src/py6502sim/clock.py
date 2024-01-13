"""
Simulator definitions and functions for a timing clock
"""
import time

class Clock:
    """
    Class definition for a timing clock
    """
    def __init__(self, frequency: int) -> None:
        self.frequency = frequency # In Hertz. I.e. 1_000_000 indicates 1MHz
        self.period = 1/frequency
        self.last_timestamp = time.perf_counter()

    def wait_for_pulse(self):
        """
        Function that returns only on the next clock pulse
        """
        dt = time.perf_counter() - self.last_timestamp
        if dt < self.period:
            time.sleep(self.period - dt)
        self.last_timestamp = time.perf_counter()
