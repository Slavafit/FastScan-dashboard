$ErrorActionPreference = "Stop"

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed --name FastScanDashboardWidget widget.py

Write-Host "Widget created: desktop-widget\dist\FastScanDashboardWidget.exe"
