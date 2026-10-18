@echo off
setlocal
if defined VCToolsInstallDir goto ready
if exist C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat call C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat >nul
if defined VCToolsInstallDir goto ready
echo Run from an x64 Visual Studio developer prompt. 1>&2
exit /b 1
:ready
set NATIVE=%~dp0
set OUT=%NATIVE%..\translate_backend\wetype\native
set OBJ=%NATIVE%..\..\.cache\native-build
if not exist "%OUT%" mkdir "%OUT%"
if not exist "%OBJ%" mkdir "%OBJ%"
cd /d "%OBJ%"
set MH=%NATIVE%vendor\minhook
cl /nologo /utf-8 /W3 /O2 /MT /LD /I"%MH%\include" "%NATIVE%observer.c" "%MH%\src\buffer.c" "%MH%\src\hook.c" "%MH%\src\trampoline.c" "%MH%\src\hde\hde64.c" /link user32.lib /OUT:"%OBJ%\TranslateObserver.dll"
if errorlevel 1 exit /b 1
python "%NATIVE%select_observer.py" "%OBJ%\TranslateObserver.dll" "%OUT%"
if errorlevel 1 exit /b 1
cl /nologo /utf-8 /W3 /O2 /MT "%NATIVE%injector.c" /link /OUT:"%OUT%\TranslateInject.exe"
if errorlevel 1 exit /b 1
if not "%~1"=="--tests" exit /b 0
if not exist "%NATIVE%..\..\.cache\feasibility-bin" mkdir "%NATIVE%..\..\.cache\feasibility-bin"
cl /nologo /utf-8 /W3 /O2 /MT "%NATIVE%tests\fixture.c" /link psapi.lib /OUT:"%NATIVE%..\..\.cache\feasibility-bin\feasibility_fixture.exe"
exit /b %ERRORLEVEL%
