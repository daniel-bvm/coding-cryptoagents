find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf market-research.zip
zip -r market-research.zip agent Dockerfile requirements.txt main.py mcps greeting.txt public