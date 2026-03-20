# Start from the official LiteLLM image
FROM ghcr.io/berriai/litellm:main-latest

# Set the working directory (LiteLLM expects things in /app)
WORKDIR /app

# Copy your custom plugin into the container
COPY custom_plugin.py /app/custom_plugin.py

# OPTIONAL: If your custom plugin requires extra Python packages, 
# you would uncomment these lines and add a requirements.txt file next to your Dockerfile.
# COPY requirements.txt /app/requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

# We don't need to define an ENTRYPOINT or CMD because the base image 
# already handles starting the proxy.