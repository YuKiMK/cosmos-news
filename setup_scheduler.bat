@echo off
setlocal
set TASK_DIR=%~dp0
if "%TASK_DIR:~-1%"=="\" set TASK_DIR=%TASK_DIR:~0,-1%

echo ================================================
echo  Cosmos News - スケジューラセットアップ
echo ================================================
echo.

:: Python パッケージをインストール
echo [1/3] Pythonライブラリをインストール中...
python -m pip install feedparser anthropic
if %errorlevel% neq 0 (
    echo ERROR: pip install に失敗しました。
    pause & exit /b 1
)
echo.

:: .env ファイルの確認
if not exist "%TASK_DIR%\.env" (
    echo ERROR: .env ファイルが見つかりません。
    echo .env.example をコピーして .env を作成し、APIキーを記入してください。
    pause & exit /b 1
)
echo [2/3] .env ファイル確認 OK
echo.

echo [3/4] ファイアウォールの設定中（iPad・スマホからのアクセスに必要）...
netsh advfirewall firewall delete rule name="Cosmos News Server" >nul 2>&1
netsh advfirewall firewall add rule name="Cosmos News Server" dir=in action=allow protocol=TCP localport=8080
if %errorlevel%==0 (
    echo   [OK] ポート 8080 を開放しました
) else (
    echo   [WARN] ファイアウォール設定に失敗しました（管理者権限で再実行してください）
)
echo.

echo [4/4] タスクスケジューラに登録中...

:: 既存タスクを削除
schtasks /delete /tn "CosmosNewsMorning" /f >nul 2>&1
schtasks /delete /tn "CosmosNewsEvening" /f >nul 2>&1
schtasks /delete /tn "CosmosNewsDaily"   /f >nul 2>&1
schtasks /delete /tn "CosmosNewsServer"  /f >nul 2>&1

:: 毎日 04:30 に朝版・夕版を一括更新
schtasks /create ^
  /tn "CosmosNewsDaily" ^
  /tr "\"%TASK_DIR%\run_daily.bat\"" ^
  /sc daily /st 04:30 ^
  /ru "%USERNAME%" /f
if %errorlevel%==0 (
    echo   [OK] 毎日 04:30 に自動更新（朝版・夕版）
) else (
    echo   [ERROR] 日次更新タスクの登録に失敗しました
)

:: ログイン時にローカルサーバーを自動起動
schtasks /create ^
  /tn "CosmosNewsServer" ^
  /tr "\"%TASK_DIR%\run_server.bat\"" ^
  /sc onlogon ^
  /ru "%USERNAME%" /f /delay 0001:00
if %errorlevel%==0 (
    echo   [OK] ログイン時にローカルサーバーを自動起動
) else (
    echo   [ERROR] サーバー起動タスクの登録に失敗しました
)

echo.
echo ================================================
echo  セットアップ完了！
echo.
echo  - 毎日 04:30 に記事が自動更新されます
echo  - run_server.bat を起動するとサーバーが立ち上がります
echo  - サーバー画面に表示されたIPアドレスをiPad・スマホで開いてください
echo  - PC起動後は自動でサーバーが起動します
echo ================================================
pause
