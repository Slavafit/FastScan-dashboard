import os

import webview


dashboard_url = os.getenv("FASTSCAN_DASHBOARD_URL", "http://127.0.0.1:8080/widget")

webview.create_window(
    "FastScan Dashboard",
    dashboard_url,
    width=460,
    height=205,
    min_size=(380, 180),
    on_top=True,
    resizable=True,
    frameless=False,
)
webview.start()
