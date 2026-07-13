@echo off
REM Run this whenever clips suddenly stop working / "Requested format is not
REM available" appears. YouTube changes often; this updates yt-dlp to the latest.
cd /d "%~dp0"
echo Updating yt-dlp to the latest STABLE version...
python -m pip install -U "yt-dlp[default]"
echo.
echo yt-dlp version now:
python -m yt_dlp --version
echo.
echo If clips STILL fail with "format is not available" after this, YouTube may
echo have broken the stable build. Run the nightly (bleeding-edge) build instead:
echo.
echo     python -m pip install -U --pre "yt-dlp[default]"
echo.
echo (Copy that line, paste it here, press Enter. Nightly usually has the fix
echo  before stable does.)
echo.
pause
