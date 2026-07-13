@echo off
REM Run this whenever clips OR images suddenly stop working. It refreshes the
REM parts that depend on websites that change often (YouTube / DuckDuckGo).
cd /d "%~dp0"
echo Updating yt-dlp (YouTube) and ddgs (image search) to the latest...
python -m pip install -U "yt-dlp[default]" ddgs requests Pillow
echo.
echo yt-dlp version now:
python -m yt_dlp --version
echo.
echo If clips STILL fail with "format is not available", try the yt-dlp nightly:
echo     python -m pip install -U --pre "yt-dlp[default]"
echo.
pause
