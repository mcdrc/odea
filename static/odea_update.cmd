:: This is a drop target for files to be processed by odea in a linux shell

@ECHO OFF
for %%i in (%*) do (

@ECHO %%i
wsl I=`wpc %%i`; odea --update --derive --filename "$I"
)
pause
