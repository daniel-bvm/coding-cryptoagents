#!/bin/bash
# Build Tailwind CSS for production
echo "Building Tailwind CSS with v3.4.10..."
./tailwindcss -i ./input.css -o ./public/tailwind.css --minify
echo "Tailwind CSS built successfully!"
