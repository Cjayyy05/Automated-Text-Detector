import pytest


def pytest_addoption(parser):
    parser.addoption("--run-ocr", action="store_true", help="Run real offline ONNX inference tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-ocr"):
        marker = pytest.mark.skip(reason="Use --run-ocr for local-model integration tests")
        for item in items:
            if "ocr" in item.keywords:
                item.add_marker(marker)
