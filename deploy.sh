docker login -u danieltn11
docker buildx build -t danieltn11/opencode:1.0.0 -f Dockerfile.prebuild --platform linux/amd64 --push
docker buildx build -t danieltn11/opencode:1.0.0 -f Dockerfile.prebuild --platform linux/amd64,linux/arm64 . --push