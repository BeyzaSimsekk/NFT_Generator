#!/usr/bin/env python3
"""
Pixel Cat NFT generator — simplified & complete version for your needs.

- No weights (equal probability).
- Uniqueness ensured by SHA256 of selected assets + color.
- Optional palette (if config.json has palette entries they are used; otherwise random RGB).
- Optional masks/ folder. If absent, mask is derived from base or cat layer.
"""

import os
import json
import random
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from PIL import Image
from tqdm import tqdm

# ------------------ Utilities ------------------