@echo off
REM ============================================================
REM  xnb_asset_batch.bat
REM  Drag and drop ANY of this game's .xnb assets (or their
REM  decompiled counterparts: .png, .tex.png, .gltf, .bin) onto
REM  this .bat file to convert them:
REM     .xnb                ->  .png / .tex.png / .gltf / .bin
REM     .png / .tex.png / .gltf / .bin  ->  .xnb
REM  The tool auto-detects which of the four asset kinds each
REM  file is. Output files are written next to the input, same
REM  base file name.
REM
REM  IMPORTANT: stock Texture2D "thumbnail" images decompile as
REM  ".tex.png" (double extension), not plain ".png" - that's how
REM  the tool tells them apart from the custom QOI images, which
REM  stay plain ".png". Keep the ".tex.png" ending intact on any
REM  file you want recompiled as a stock texture.
REM ============================================================

setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install it from https://www.python.org/downloads/ ^(check "Add to PATH" during setup^)
    echo then run this file again.
    pause
    exit /b 1
)

python -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Pillow is not installed - installing it now...
    python -m pip install --quiet pillow
)

if "%~1"=="" (
    echo Usage: drag and drop one or more .xnb / .png / .tex.png /
    echo        .gltf / .bin files ^(or folders^) onto this .bat file.
    pause
    exit /b 0
)

python "%~dp0xnb_asset_tool.py" %*

echo.
echo Done.
pause
