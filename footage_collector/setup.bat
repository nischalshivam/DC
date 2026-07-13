@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo    Footage Collector  -  one-time setup
echo ================================================
echo.

REM --- 1) check Python ---
where python >nul 2>&1
if errorlevel 1 (
  echo [X] Python nahi mila.
  echo     1^) https://www.python.org/downloads/  se Python 3.10+ install karo
  echo     2^) install karte waqt "Add python.exe to PATH" tick karna ZAROORI hai
  echo     3^) phir ye setup.bat dobara double-click karo
  echo.
  pause
  exit /b 1
)

echo [1/3] Python packages install ho rahe hain...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -U yt-dlp
if errorlevel 1 (
  echo [X] pip install fail hua. Internet check karo aur dobara try karo.
  pause
  exit /b 1
)

echo.
echo [2/3] ffmpeg setup...
if exist "bin\ffmpeg.exe" (
  echo     ffmpeg pehle se hai, skip.
) else (
  if not exist "bin" mkdir bin
  echo     ffmpeg download ho raha hai ^(1-2 min lag sakte hain^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$u='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';" ^
    "Invoke-WebRequest -Uri $u -OutFile 'ffmpeg.zip';" ^
    "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_tmp' -Force;" ^
    "$f=Get-ChildItem -Path 'ffmpeg_tmp' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1;" ^
    "Copy-Item $f.FullName 'bin\ffmpeg.exe' -Force;" ^
    "Copy-Item (Join-Path $f.DirectoryName 'ffprobe.exe') 'bin\ffprobe.exe' -Force;" ^
    "Remove-Item 'ffmpeg.zip','ffmpeg_tmp' -Recurse -Force"
  if errorlevel 1 (
    echo [X] ffmpeg auto-download fail hua. SETUP_GUIDE.md me manual steps dekho.
    pause
    exit /b 1
  )
)

echo.
echo [3/3] Ho gaya!  Ab "run.bat" double-click karke app kholo.
echo.
pause
