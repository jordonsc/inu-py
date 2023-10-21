class RangingSensor:
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
    async def read_loop(self):
        """
        Starts the sensor reading loop.
        """
        pass

    def is_motion(self) -> bool:
        """
        Returns the distance in mm.

        Returns None if no measurement has been made.
        """
        pass
