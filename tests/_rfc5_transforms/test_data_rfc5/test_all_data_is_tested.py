import importlib
import os
from pathlib import Path

import pytest

from tests._rfc5_transforms.conftest import TESTS_FILE_TO_DATA_MAPPING


@pytest.mark.parametrize("test_file, data_folder", TESTS_FILE_TO_DATA_MAPPING.items())
def test_all_files_have_functions(test_file: str, data_folder: str) -> None:
    json_files = [
        f
        for f in os.listdir(Path(__file__).parent.parent / data_folder)
        if f.endswith(".json")
    ]

    module = importlib.import_module(
        "tests._rfc5_transforms." + test_file.replace(".py", "").replace("/", ".")
    )
    test_functions = [name for name in module.__dir__() if name.startswith("test_")]

    missing_functions = []

    for json_file in json_files:
        test_name = f"test_{json_file.replace('.json', '')}"
        if test_name not in test_functions:
            missing_functions.append(json_file)

    if missing_functions:
        print("Missing test functions for the following JSON files:")
        for missing in missing_functions:
            print(f"- {missing}")
        raise AssertionError("Some test functions are missing.")
