@echo off
chcp 65001 >nul
title HSK 5급 분석기
cd /d "%~dp0"

:MENU
echo.
echo  ========================================
echo    HSK 5급 중국어 분석기
echo  ========================================
echo.
echo  [1] 결과 보기 (듣기)
echo  [2] 결과 보기 (단어)
echo  [3] 듣기 전체 분석 (100트랙)
echo  [4] 듣기 일부 분석 (범위 지정)
echo  [5] 단어 전체 분석 (2500개)
echo  [6] 단어 일부 분석 (범위 지정)
echo  [7] 단일 트랙 분석
echo  [8] 캐시 무시 재분석 (단일)
echo  [0] 종료
echo.
set /p choice="  선택: "

if "%choice%"=="1" goto VIEW_LISTENING
if "%choice%"=="2" goto VIEW_VOCAB
if "%choice%"=="3" goto RUN_LISTENING_ALL
if "%choice%"=="4" goto RUN_LISTENING_RANGE
if "%choice%"=="5" goto RUN_VOCAB_ALL
if "%choice%"=="6" goto RUN_VOCAB_RANGE
if "%choice%"=="7" goto RUN_SINGLE
if "%choice%"=="8" goto RUN_FORCE
if "%choice%"=="0" exit
goto MENU

:VIEW_LISTENING
if exist "output\listening.html" (
    start "" "output\listening.html"
    echo  브라우저에서 열었습니다.
) else (
    echo  아직 분석 결과가 없습니다. 먼저 분석을 실행하세요.
)
goto MENU

:VIEW_VOCAB
if exist "output\vocabulary.html" (
    start "" "output\vocabulary.html"
    echo  브라우저에서 열었습니다.
) else (
    echo  아직 분석 결과가 없습니다. 먼저 분석을 실행하세요.
)
goto MENU

:RUN_LISTENING_ALL
echo  듣기 전체 분석을 시작합니다...
call venv\Scripts\activate.bat
python run.py --source listening --all
start "" "output\listening.html"
goto MENU

:RUN_LISTENING_RANGE
set /p start_n="  시작 번호: "
set /p end_n="  끝 번호: "
echo  TRACK%start_n% ~ TRACK%end_n% 분석 시작...
call venv\Scripts\activate.bat
python run.py --source listening --range %start_n% %end_n%
start "" "output\listening.html"
goto MENU

:RUN_VOCAB_ALL
echo  단어 전체 분석을 시작합니다...
call venv\Scripts\activate.bat
python run.py --source vocabulary --all
start "" "output\vocabulary.html"
goto MENU

:RUN_VOCAB_RANGE
set /p start_n="  시작 번호: "
set /p end_n="  끝 번호: "
echo  %start_n% ~ %end_n% 분석 시작...
call venv\Scripts\activate.bat
python run.py --source vocabulary --range %start_n% %end_n%
start "" "output\vocabulary.html"
goto MENU

:RUN_SINGLE
set /p track_file="  파일명 (예: TRACK001.mp3): "
call venv\Scripts\activate.bat
python run.py --track %track_file%
start "" "output\listening.html"
goto MENU

:RUN_FORCE
set /p track_file="  파일명 (예: TRACK001.mp3): "
call venv\Scripts\activate.bat
python run.py --force --track %track_file%
start "" "output\listening.html"
goto MENU
