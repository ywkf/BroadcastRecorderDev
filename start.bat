@echo off
:: 强制UTF-8编码环境
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: 设置Anaconda路径
set ANACONDA_PATH=D:\Anaconda3
set PROJECT_PATH=D:\PythonPro\BroadcastRecorder_dev

:: 激活conda环境
call "%ANACONDA_PATH%\Scripts\activate.bat" gr_py310

:: 设置关键环境变量
set PYTHONPATH=%PROJECT_PATH%
set CONDA_PREFIX=%ANACONDA_PATH%\envs\gr_py310

:: 进入项目目录
cd /d "%PROJECT_PATH%"

:: 启动主程序（强制UTF-8模式）
"%ANACONDA_PATH%\envs\gr_py310\python.exe" -X utf8 main_gui.py

pause
