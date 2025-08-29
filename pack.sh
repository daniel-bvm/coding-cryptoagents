find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

output_file_name="eli5.zip"
rm -rf $output_file_name
zip -r $output_file_name agent Dockerfile requirements.txt main.py mcps greeting.txt public
echo "Packed $output_file_name"