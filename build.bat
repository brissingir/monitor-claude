@echo off
pip install pyinstaller
pyinstaller --onefile --windowed --name="ClaudeUsageMonitor" main.py
echo.
echo Built: dist\ClaudeUsageMonitor.exe
pause
