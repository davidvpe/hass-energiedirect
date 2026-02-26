from datetime import timedelta


def bucket_time(ts, bucket_size):
    """
    Get the bucket time for the interval.

    e.g. for a bucket size of 60 minutes, the time 10:07 would be rounded down to 10:00.
    """
    return ts - timedelta(
        minutes=ts.minute % bucket_size, seconds=ts.second, microseconds=ts.microsecond
    )
