#!/usr/bin/env python3
import http.server
import socketserver
import os

# Ensure the static directory exists
os.makedirs("static", exist_ok=True)

# Define the port to serve on
PORT = 8081

# Set up handler
Handler = http.server.SimpleHTTPRequestHandler

# Set the directory to serve files from
os.chdir("static")

# Create server
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT} - Open http://localhost:{PORT} in your browser")
    
    # Serve until interrupted
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped by user")
