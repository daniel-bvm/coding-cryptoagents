find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf coding-cryptoagent-qwen.zip
zip -r coding-cryptoagent-qwen.zip agent Dockerfile requirements.txt main.py .tmux.conf