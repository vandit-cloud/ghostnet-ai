"""Suite-wide test environment.

The net segmentation model is OFF for every test unless a test configures one
explicitly (Settings(net_weights_path=...)). Otherwise any Settings() resolves
a promoted ai/models/trained/ghostnet_net.pt when one exists, and tests of the
box-detector path would silently run the real U-Net -- passing or failing
depending on which machine they run on.

Set at import time, not in a fixture: test modules build Settings objects (and
ghostnet.config builds SETTINGS) when they are imported, before any fixture
runs.
"""

import os

os.environ["GHOSTNET_NET_WEIGHTS"] = "none"
