:: This is a drop target for files to be processed by odea in a linux shell
:: If using a graphical editor, make sure to run an X server in Windows (e.g., Xming)

@ECHO OFF
for %%i in (%*) do (

@ECHO %%i
wsl I=`wpc %%i`; odea --edit --filename="$I"
)

pause
