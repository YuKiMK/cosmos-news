@echo off
cd /d "%~dp0"
python update_news.py --edition evening >> update_log.txt 2>&1
