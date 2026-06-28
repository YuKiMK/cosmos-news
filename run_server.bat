@echo off
cd /d "%~dp0"
echo.
echo  Cosmos News サーバーを起動します...
echo  IPアドレスは起動後の画面に表示されます。
echo  このウィンドウは開いたままにしてください。
echo.
python server.py
pause
