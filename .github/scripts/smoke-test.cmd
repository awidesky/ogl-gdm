@echo off
rem Runs smoke-test.ps1 with the PowerShell execution policy bypassed for this run only
rem (nothing is changed permanently), so "running scripts is disabled" cannot happen.
rem Usage: smoke-test.cmd [log.txt] [-List] [-Timed N] [-DefenderBypass]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke-test.ps1" %*
exit /b %ERRORLEVEL%
