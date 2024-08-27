class RangingSensor:
    """
    A ranging sensor measures the distance from the sensor to a point in front of it. The application can use this
    distance to detect an object relative to the idle distance.
    """

    async def read_loop(self):
        """
        Starts the sensor reading loop.
        """
        pass

    def get_distance(self) -> int | None:
        """
        Returns the distance in mm.

        Returns None if no measurement has been made.
        """
        pass

    def get_age(self) -> float | None:
        """
        Returns the number of seconds since the last valid measurement.

        Returns None if no measurement has been made.
        """
        pass


class MotionSensor:
    """
    A motion sensor is a dumb binary sensor that either detects motion, or it doesn't. No additional information is
    provided by this sensor type.
    """

    async def read_loop(self):
        """
        Starts the sensor reading loop.
        """
        pass

    def is_motion(self) -> bool:
        """
        Returns true if the sensor is detecting motion
        """
        pass


class RadarState:
    def __init__(self):
        # a body is detected by the sensor
        self.presence = False

        # the detected body is moving (true), still (false) or not detected (None)
        self.motion = None

        # the speed in which a body is moving (1-100)
        self.speed = None

        # the direction in which the body is moving (none = unknown, true = towards, false = away)
        self.direction = None

    def is_present(self) -> bool:
        """
        Returns true if a body is detected by the sensor.
        """
        return self.presence

    def is_moving(self) -> bool | None:
        """
        Returns true if a detected presence is moving. If the body is still, then this will return false.

        Returns None if there is no body detected.
        """
        return self.motion

    def get_speed(self) -> int | None:
        """
        Returns the speed in which a body is moving.

        Unit is a value between 1 and 100 representing the speed of the body relative to the sensors capabilities.

        Returns None if there is no body detected.
        """
        return self.speed

    def get_direction(self) -> bool | None:
        """
        Returns the direction (true == towards sensor, false == away) in which the body is moving.

        Returns None if there is no body detected, the body is idle or unable to determine.
        """
        return self.direction

    def __str__(self):
        if self.motion is None:
            return "No subject"
        elif self.motion is False:
            return "Idle"
        elif self.motion is True:
            if self.direction is None:
                suffix = ""
            elif self.direction is True:
                suffix = " <"
            else:
                suffix = " >"

            return f"Active ({self.get_speed()}){suffix}"
        else:
            return "Unknown"

    def clear_subject(self):
        self.presence = False
        self.motion = None
        self.speed = None
        self.direction = None


class RadarSensor:
    """
    A radar sensor is a more advanced sensor that can detect motion, distance, and speed of an object in front of it.
    """

    def __init__(self):
        self.radar = RadarState()

    async def read_loop(self):
        """
        Starts the sensor reading loop.
        """
        pass

    def is_present(self) -> bool:
        """
        Returns true if the sensor is detecting motion
        """
        return self.radar.is_moving()

    def is_active(self) -> bool | None:
        """
        Returns true if the detected body is moving, false if it is idle and None if there is no body detected.
        """
        return self.radar.is_moving()

    def get_radar(self) -> RadarState:
        """
        Returns the current state of the radar sensor.
        """
        return self.radar

    async def calibrate(self, cfg: dict):
        """
        Calibrates the radar sensor with the given configuration.
        """
        pass
