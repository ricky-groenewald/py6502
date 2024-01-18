"""
Simulator definitions and functions for a timing clock

Only accurate for low frequencies. ~10kHz
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
        next_time = self.last_timestamp + self.period
        dt = time.perf_counter()
        while dt < next_time:
            dt = time.perf_counter()
        self.last_timestamp = time.perf_counter()
