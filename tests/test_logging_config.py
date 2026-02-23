import logging

from logging_config import setup_logging


def test_minimal_werkzeug_filter_allows_startup_and_warnings_blocks_info_noise():
    setup_logging("INFO")
    werkzeug_logger = logging.getLogger("werkzeug")
    assert werkzeug_logger.filters, "Expected at least one werkzeug filter"

    test_filter = werkzeug_logger.filters[-1]

    startup_record = logging.LogRecord(
        name="werkzeug",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Running on http://127.0.0.1:5000",
        args=(),
        exc_info=None,
    )
    info_noise_record = logging.LogRecord(
        name="werkzeug",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET /static/js/chessboard-init.js HTTP/1.1",
        args=(),
        exc_info=None,
    )
    warning_record = logging.LogRecord(
        name="werkzeug",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Potential issue in request handling",
        args=(),
        exc_info=None,
    )

    assert test_filter.filter(startup_record) is True
    assert test_filter.filter(info_noise_record) is False
    assert test_filter.filter(warning_record) is True
