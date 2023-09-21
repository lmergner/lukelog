import logging

LOG_TREE = False
try:
    from logging_tree import printout as __logging_tree_printout
    LOG_TREE = True
except ImportError:
    pass

COLORAMA_LIB = False
try:
    import colorama
    COLORAMA = True
except ImportError:
    pass


__LOGGER_LOWER_BOUND = 2


VERBOSITY_INTS = {
    0: logging.CRITICAL,
    1: logging.ERROR,
    2: logging.WARNING,
    3: logging.INFO,
    4: logging.DEBUG,
}


def _log_level_name(lvl, lower_bound=__LOGGER_LOWER_BOUND):
    """ Given an integer from a verbosity count, return a logging.LEVEL """

    # offset from a reasonable amount of verbosity
    lvl += lower_bound

    # but makes sure we don't exceed the max
    upper_bound = max(VERBOSITY_INTS.keys())
    if lvl > upper_bound:
        lvl = upper_bound

    return VERBOSITY_INTS.get(lvl, lower_bound)


def _add_logging_level(level_name, level_number, method_name=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `level_name` becomes an attribute of the `logging` module with the value
    `level_number`. `method_name` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `method_name` is not specified, `level_name.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5


    Note / Attribution
    ------------------
    https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility/35804945#35804945
    """
    level_name = level_name.upper()

    if not method_name:
        method_name = level_name.lower()

    if hasattr(logging, level_name):
        raise AttributeError('{} already defined in logging module'.format(level_name))
    if hasattr(logging, method_name):
        raise AttributeError('{} already defined in logging module'.format(method_name))
    if hasattr(logging.getLoggerClass(), method_name):
        raise AttributeError('{} already defined in logger class'.format(method_name))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(level_number):
            self._log(level_number, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(level_number, message, *args, **kwargs)

    logging.addLevelName(level_number, level_name)
    setattr(logging, level_name, level_number)
    setattr(logging.getLoggerClass(), method_name, logForLevel)
    setattr(logging, method_name, logToRoot)

    # library specific additions
    VERBOSITY_INTS[level_number] = getattr(logging, level_name)


def setup_logging(logger_name, verbosity, syslog=False, newline=False, sync_logs_list=[]):
    """setup colored logging"""

    logger = logging.getLogger(logger_name)
    # _add_logging_level("trace", 5)

    if COLORAMA:
        colorama.init()

        # Note: if you are seeing duplicate logging messages, you
        # probably called logging.<logLevel>(<msg>) which enables
        # the root logger. Change "logging" to "logger".

        RESET = colorama.Style.RESET_ALL  # "\033[0m"
        BOLD = colorama.Style.BRIGHT  # "\033[1m"

        # https://docs.python.org/3/library/logging.html#logging-levels
        COLOR_MAP = {
            # BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
            0: colorama.Fore.WHITE,  # NOTSET
            5:  colorama.Fore.LIGHTMAGENTA_EX, # Trace
            10: colorama.Fore.CYAN,  #  DEBUG
            20: colorama.Fore.GREEN,  # INFO
            30: colorama.Fore.YELLOW,  # yellow
            40: colorama.Fore.RED,  # red
            50: colorama.Fore.MAGENTA,  # bold red?
        }

        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.color = COLOR_MAP.get(record.levelno)
            record.reset = RESET
            record.bold = BOLD
            return record

        logging.setLogRecordFactory(record_factory)

        log_format = "%(color)s[%(levelName)s]%(reset)s [%(name)s] [%(filename)s:%(lineno)d@%(funcName)s] %(bold)s%(message)s%(reset)s "
    else:
        log_format = "[%(level_name)s] [%(name)s] [%(filename)s:%(lineno)d@%(funcName)s] %(message)s "

    # END COLORAMA SETUP

    logger.setLevel(_log_level_name(verbosity))
    ch = logging.StreamHandler()
    ch.setLevel(_log_level_name(verbosity))

    # create formatter

    if newline:
        log_format += "\n"
    formatter = logging.Formatter(log_format)

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    for log in sync_logs_list:
        log = logging.getLogger(log)
        log.setLevel(_log_level_name(verbosity))
        log.addHandler(ch)

    if syslog:
        logger.addHandler(logging.handlers.SysLogHandler(address=syslog))

    if LOG_TREE:
        __logging_tree_printout()

