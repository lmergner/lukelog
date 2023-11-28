import logging
import os
from importlib import reload

import pytest

from lukelog import add_logging_level, setup_logging
from lukelog.log import _get_levelname_from_verbosity

LOGNAME = 'lukelog_testing'


def reset_logging_func():
    # if LOGNAME in logging.Logger.manager.loggerDict.keys():
    #     logger = logging.getLogger(LOGNAME)
    #     for handler in logger.handlers[:]:
    #         logger.removeHandler(logger.handlers[0])
    #     del logger
    #     logging.Logger.manager.loggerDict.pop(LOGNAME)

    logging.shutdown()
    reload(logging)

@pytest.fixture
def reset_logging():
    reset_logging_func()
    yield
    reset_logging_func()


level_data = [
    (10, logging.DEBUG),
    (5, logging.DEBUG),
    (4, logging.INFO),
    (3, logging.WARNING),
    (2, logging.ERROR),
    (1, logging.CRITICAL),
    (0, logging.CRITICAL),
    (-1, logging.CRITICAL),
]

custom_level_data = [
    (5, 'trace'),
    (45, 'blarg')
]

@pytest.mark.parametrize('verbosity, level', level_data)
def test_logging_level_limits(reset_logging, verbosity, level):
    assert _get_levelname_from_verbosity(verbosity) == level


@pytest.mark.parametrize('lvlint, lvlname', custom_level_data)
def test_add_custom_logging_levels(reset_logging, lvlname, lvlint):
    add_logging_level(lvlname, lvlint)
    assert getattr(logging, lvlname.upper()) == lvlint


@pytest.mark.parametrize('verbosity, level', level_data)
def test_setup_logging_w_string(reset_logging, caplog, verbosity, level):
    setup_logging(LOGNAME, verbosity)
    assert LOGNAME in logging.Logger.manager.loggerDict.keys()
    logger = logging.getLogger(LOGNAME)
    assert logger.hasHandlers()
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert logger.getEffectiveLevel() == level

@pytest.mark.parametrize('lvlint, lvlname', custom_level_data)
def test_setup_logging_w_custom_levels(reset_logging, caplog, lvlname, lvlint):
    add_logging_level(lvlname, lvlint)
    setup_logging(LOGNAME, 5)
    faculty = getattr(logging, lvlname.lower())
    faculty("This is a lukelog message.")
    for record in caplog.records:
        assert record.levelname != lvlname.upper()
    assert "lukelog message" in caplog.text


