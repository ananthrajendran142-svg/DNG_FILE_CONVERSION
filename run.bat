@echo off
title DGN to PDF Studio Server
echo ========================================================
echo           DGN to PDF Studio - Web Application
echo ========================================================
echo.
echo Starting Web Server on http://localhost:5000 ...
echo.
start "" "http://localhost:5000"
"C:\Users\anant\Python312\python.exe" app.py
pause
