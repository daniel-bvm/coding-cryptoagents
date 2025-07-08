find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf coding-cryptoagent.zip
zip -r coding-cryptoagent.zip agent Dockerfile requirements.txt  main.py