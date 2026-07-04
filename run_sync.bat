@echo off
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" sync_to_supabase.py >> sync_log.txt 2>&1
