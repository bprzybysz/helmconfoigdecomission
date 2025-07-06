# Use an official Python runtime as a parent image
FROM python:3.10-slim-buster

# Define build argument for environment
ARG ENV=dev

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app



# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Set the entrypoint to our custom shell script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command to pass to the entrypoint (if no other command is given)
CMD []
