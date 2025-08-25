from danieltn11/opencode:1.0.0

workdir /workspace
copy main.py main.py
copy agent agent
copy .tmux.conf .tmux.conf

expose 7681
cmd ["python", "main.py"]