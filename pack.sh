find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf slide-maker.zip
zip -r slide-maker.zip agent Dockerfile requirements.txt main.py mcps greeting.txt public