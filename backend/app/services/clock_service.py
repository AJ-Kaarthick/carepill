from datetime import datetime, timedelta
from typing import Optional

class SystemClock:
    """
    Virtual Clock service supporting deterministic test time travel
    and real UTC time.
    """
    def __init__(self):
        self._time_offset: timedelta = timedelta(0)
        self._frozen_time: Optional[datetime] = None

    def now(self) -> datetime:
        if self._frozen_time is not None:
            return self._frozen_time
        return datetime.utcnow() + self._time_offset

    def advance_minutes(self, minutes: int) -> datetime:
        if self._frozen_time is not None:
            self._frozen_time += timedelta(minutes=minutes)
            return self._frozen_time
        self._time_offset += timedelta(minutes=minutes)
        return self.now()

    def advance_seconds(self, seconds: int) -> datetime:
        if self._frozen_time is not None:
            self._frozen_time += timedelta(seconds=seconds)
            return self._frozen_time
        self._time_offset += timedelta(seconds=seconds)
        return self.now()

    def set_time(self, dt: datetime):
        self._frozen_time = dt

    def reset(self):
        self._time_offset = timedelta(0)
        self._frozen_time = None

system_clock = SystemClock()
