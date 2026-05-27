"""Logging utilities"""

import logging


class IgnoreVariableDoesNotExist(logging.Filter):
    """
    Filter to ignore VariableDoesNotExist errors

    We intentionally pass nonexistent variables to templates a lot, so
    these errors are not useful to us.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            (_, err_value, _) = record.exc_info
            while err_value:
                if type(err_value).__name__ == "VariableDoesNotExist":
                    return False
                err_value = err_value.__context__
        return True


class SkipUnsignedGetErrors(logging.Filter):
    """
    UnsignedGetRequest is a custom error for PermissionDenied
    exceptions when we require signed get requests.

    This allows us to ignore these "errors" since they are expected
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            (_, err_value, _) = record.exc_info
            while err_value:
                if type(err_value).__name__ == "UnsignedGetRequest":
                    return False
                err_value = err_value.__context__
        return True
