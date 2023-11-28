import logging
import os
import platform
from collections import OrderedDict
from logging.handlers import SysLogHandler
from typing import List, Optional

import colorama

__LOWEST_VERBOSITY = int(os.environ.get("LUKELOG_LOWEST_VERBOSITY", 0))
__LOG_FORMAT = (
    '%(color)s[%(levelName)s]%(reset)s '
    '[%(name)s] '
    '{%(filename)s:%(lineno)d@%(funcName)s} '
    '%(msg_style)s%(message)s%(reset)s '
)


class LukeLogError(Exception): ...



# TODO: Convert color map to UserDict?
# https://docs.python.org/3/library/logging.html#logging-levels
__COLOR_TO_LEVEL_MAP = {
    # BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
    0: colorama.Fore.WHITE,  # NOTSET
    5: colorama.Fore.WHITE + colorama.Style.BRIGHT,  # Trace
    10: colorama.Fore.CYAN,  #  DEBUG
    15: colorama.Fore.CYAN + colorama.Style.BRIGHT,
    20: colorama.Fore.GREEN,  # INFO
    25: colorama.Fore.GREEN + colorama.Style.BRIGHT,
    30: colorama.Fore.YELLOW,  # yellow
    35: colorama.Fore.YELLOW + colorama.Style.BRIGHT,
    40: colorama.Fore.MAGENTA, # bold red?
    45: colorama.Fore.MAGENTA + colorama.Style.BRIGHT,
    50: colorama.Fore.RED,  # red
    55: colorama.Fore.RED + colorama.Style.BRIGHT,
}


def _get_levelname_from_verbosity(lvl: int, lower_bound: int = __LOWEST_VERBOSITY):
    """Given an integer from a verbosity count, return a logging.LEVEL"""

    levels = OrderedDict({ v: k for k, v in logging.getLevelNamesMapping().items()})
    levels.pop(0)
    sorted_level_keys = sorted(levels.keys())

    if lvl < lower_bound:
        lvl = lower_bound
    if lvl == 0:
        lvl += 1

    # make sure we don't exceed the length of the list
    upper_bound = len(sorted_level_keys)
    if lvl > upper_bound:
        lvl = upper_bound

    # [10, 20, 30, 40, 50]
    #   0   1   2   3   4
    #  -5  -4   -3  -2  -1
    return getattr(logging, levels[sorted_level_keys[-lvl]])


def add_logging_level(
    level_name: str,
    level_number: int,
    method_name: Optional[str] = None
):
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


def setup_logging(
    logger_name: str | logging.Logger,
    verbosity: int,
    log_format: str = __LOG_FORMAT,
    syslog: bool = False,
    newline: bool = False,
    sync_logs_list: List[str] = []
):
    """setup logging

    :param logger_name: The name of the logger object or the :py:mod:`logging.Logger`
                        object to modify.
    :type logger_name: string | logging.Logger
    :param verbosity: How verbose should logging be; corresponds to the index of a list
                      of sorted logging levels.
    :type logger_name: int
    :param syslog: flag for adding a syslog handler to the logger
    :type syslog: bool
    :param newline: add a newline character to the end of every log message;
                    modifies the :py:mod:`logging.Formatter` object
    :type newline: bool
    :param sync_logs_list: a list of logger faculties to normalize to our levels,
                           handlers, and formatters
    :type sync_logs_list: List[str]

    """

    colorama.init()

    logger = (
        logging.getLogger(logger_name)
        if not isinstance(logger_name, logging.Logger)
        else logger_name
    )

    # COLOR RECORDS
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.color = __COLOR_TO_LEVEL_MAP.get(record.levelno)
        record.reset = colorama.Style.RESET_ALL  # "\033[0m"
        record.msg_style = colorama.Style.BRIGHT  # "\033[1m"
        return record

    logging.setLogRecordFactory(record_factory)
    # END COLOR RECORDS

    logger.setLevel(_get_levelname_from_verbosity(verbosity))
    ch = logging.StreamHandler()
    ch.setLevel(_get_levelname_from_verbosity(verbosity))

    # create formatter

    if newline:
        log_format += '\n'
    formatter = logging.Formatter(log_format)

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    for log in sync_logs_list:
        log = logging.getLogger(log)
        log.setLevel(_get_levelname_from_verbosity(verbosity))
        log.addHandler(ch)

    if syslog:
        # NOTE: https://github.com/python/cpython/issues/91070
        if platform.system() == 'Darwin' or float(platform.mac_ver()[0]) >= 12.0:
            raise LukeLogError(
                "logging.handlers.SysLogHandler not longer works on MacOS 12.0 "
                "and above; see https://github.com/python/cpython/issues/91070"
            )
        else:
            logger.addHandler(SysLogHandler(address='syslog'))


