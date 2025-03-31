@echo off
echo Starting Smart Home Device Control Demo...

REM Set project root path
set PROJECT_ROOT=%~dp0..\..

REM Add project root to PYTHONPATH
set PYTHONPATH=%PROJECT_ROOT%

REM Activate virtual environment
call %PROJECT_ROOT%\.venv\Scripts\activate

REM Ensure dependencies are installed
echo Checking dependencies...
uv pip install -r %PROJECT_ROOT%\requirements.txt

REM Start server
echo Starting server...
python run.py

REM Keep window open on error
if errorlevel 1 (
    echo Error occurred! Check the logs for details.
    pause
)