"""Restricted publication service; never imports the working Shiny dashboard.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import os

from dpv_dashboard.access import protect

os.environ["DPV_ACCESS_MODE"] = "publication"
app = protect()
