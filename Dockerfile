FROM python:3.9-slim

# Install system dependencies for OpenCV and other tools
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up a working directory
WORKDIR /app

# Copy everything
COPY . /app

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn
RUN pip uninstall -y opencv-python opencv-python-headless
RUN pip install --no-cache-dir opencv-python-headless

# Expose port
EXPOSE 7860

# Run the app using Gunicorn on port 7860 (Hugging Face default)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--timeout", "1000", "app:app"]
