echo "Pynab started. You can use process manager to kill spawned processes (called python.exe)."
echo "Make sure that your PATH has python set to a python3 directory."
start python start.py
start python postprocess.py
python api.py
pause
exit