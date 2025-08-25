find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf prototype.zip
zip -r prototype.zip agent Dockerfile requirements.txt main.py mcps greeting.txt public