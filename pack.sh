find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf eli5-v1.zip
zip -r eli5-v1.zip agent Dockerfile requirements.txt main.py mcps greeting.txt public