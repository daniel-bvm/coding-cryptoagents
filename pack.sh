find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf coding-cryptoagent-opencode.zip
zip -r coding-cryptoagent-opencode.zip agent Dockerfile requirements.txt  main.py