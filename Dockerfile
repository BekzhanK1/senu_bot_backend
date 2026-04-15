FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies if needed (none required for current setup, but maybe for asyncpg later)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
