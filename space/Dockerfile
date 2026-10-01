FROM ghcr.io/danny-avila/librechat-dev:latest
EXPOSE 3080

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=3080
ENV SESSION_EXPIRY=900000
ENV REFRESH_TOKEN_EXPIRY=604800000

# Create necessary directories
# Testing this change
RUN mkdir -p /app/uploads/temp
RUN mkdir -p /app/client/public/images/temp
RUN mkdir -p /app/api/logs/
RUN mkdir -p /app/data

# Give write permission to the directory
RUN chmod -R 777 /app/uploads/temp
RUN chmod -R 777 /app/client/public/images
RUN chmod -R 777 /app/api/logs/
RUN chmod -R 777 /app/data

# Use this Space's own librechat.yaml
COPY librechat.yaml /app/librechat.yaml

# Install dependencies
RUN cd /app/api && npm install

# Command to run on container start
CMD ["npm", "run", "backend"]