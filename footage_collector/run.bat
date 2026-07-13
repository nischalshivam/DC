@echo off
cd /d "%~dp0"
python gui.py
if errorlevel 1 (
  echo.
  echo App band ho gaya / error aaya. Upar message padho.
  echo Agar "Python nahi mila" type error hai to pehle setup.bat chalao.
  pause
)
