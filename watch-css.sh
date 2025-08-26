#!/bin/bash
# Watch and rebuild Tailwind CSS during development
echo "Starting Tailwind CSS watcher (v3.4.10)..."
./tailwindcss -i ./input.css -o ./public/tailwind.css --watch
