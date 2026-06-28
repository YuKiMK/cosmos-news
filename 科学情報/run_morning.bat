@echo off
cd /d "%~dp0"
python update_news.py --edition morning >> update_log.txt 2>&1
