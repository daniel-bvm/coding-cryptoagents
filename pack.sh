find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

rm -rf prompt-based-opencode.zip
zip -r prompt-based-opencode.zip agent Dockerfile requirements.txt main.py mcps greeting.txt public