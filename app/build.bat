@echo off
REM OpsHub Agent EXE 빌드 스크립트

echo ========================================
echo OpsHub Agent EXE 빌드 시작
echo ========================================

cd /d %~dp0

REM PyInstaller 설치 확인
echo.
echo PyInstaller 설치 확인 중...
python -m pip install pyinstaller --upgrade

REM 빌드 디렉토리 정리
echo.
echo 빌드 디렉토리 정리 중...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__
if exist *.spec del /q *.spec

REM PyInstaller로 EXE 빌드
echo.
echo EXE 빌드 중...
pyinstaller --onefile ^
    --name OpsHubAgent ^
    --console ^
    --hidden-import=requests ^
    --hidden-import=win32timezone ^
    --hidden-import=win32api ^
    --hidden-import=win32con ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageDraw ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=win32service ^
    --hidden-import=win32serviceutil ^
    --hidden-import=servicemanager ^
    --hidden-import=psutil ^
    --collect-all PyQt6 ^
    --collect-all pystray ^
    --collect-all requests ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo 빌드 완료!
    echo EXE 파일 위치: dist\OpsHubAgent.exe
    echo ========================================
    echo.
    echo 빌드된 EXE 파일을 테스트하려면:
    echo   dist\OpsHubAgent.exe
    echo.
) else (
    echo.
    echo ========================================
    echo 빌드 실패!
    echo ========================================
    pause
    exit /b 1
)

pause

