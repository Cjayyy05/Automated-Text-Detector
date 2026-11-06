"""Read-only Windows display inventory command."""

import argparse
import json
from pathlib import Path

from stream_code_capture.display_inventory import (
    ColorInfo2 as ColorInfo2,
)
from stream_code_capture.display_inventory import (
    DisplayPath as DisplayPath,
)
from stream_code_capture.display_inventory import (
    Header as Header,
)
from stream_code_capture.display_inventory import (
    Source as Source,
)
from stream_code_capture.display_inventory import (
    Target as Target,
)
from stream_code_capture.display_inventory import (
    inventory,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with args.report.open("x", encoding="utf-8") as report:
        result = inventory()
        json.dump(result, report, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
