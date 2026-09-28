docker buildx build --platform linux/amd64 -t myapp:latest \
  --output type=docker,dest=photo-api.tar .


#docker load -i photo-api.tar

#docker run -d photo-api:latest