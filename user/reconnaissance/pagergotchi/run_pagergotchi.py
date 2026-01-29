#!/usr/bin/env python3
"""
Pagergotchi launcher - Pwnagotchi port for WiFi Pineapple Pager
Uses native C display library and hcxdumptool for WiFi operations
"""

import sys
import os

# Add payload directory to path so imports work
payload_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, payload_dir)
sys.path.insert(0, os.path.join(payload_dir, 'lib'))

# Now import and run
from pwnagotchi_port.main import main

if __name__ == '__main__':
    sys.exit(main())
