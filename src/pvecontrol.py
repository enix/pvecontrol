#!/usr/bin/python3

import re
import sys
from pvecontrol import main # pylint: disable=import-self

if __name__ == "__main__":
    sys.argv[0] = re.sub(r"(-script\.pyw|\.exe)?$", "", sys.argv[0])
    sys.exit(main())
