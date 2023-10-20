from datetime import datetime, timezone


class Time:
    @staticmethod
    def sec_to_nano(sec: float) -> int:
        return round(sec * 10 ** 9)

    @staticmethod
    def format_timestamp(timestamp: float) -> str:
        dt = datetime.fromtimestamp(timestamp, timezone.utc)
        return dt.isoformat(sep="T")[0:19] + ".0Z"

    @staticmethod
    def format_msg_timestamp(timestamp: str) -> str:
        return Time.format_timestamp(float(f"{timestamp[:10]}.{timestamp[10:]}"))
