import logging


class IgnoreVariableDoesNotExist(logging.Filter):
    def filter(self, record):
        if(record.exc_info):
            (errType, errValue, _) = record.exc_info
            while errValue:
                if type(errValue).__name__ == 'VariableDoesNotExist':
                    return False
                errValue = errValue.__context__
            return True
