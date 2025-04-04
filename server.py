from flask import Flask, request, jsonify, send_from_directory
import subprocess
import os
import base64
import tempfile
import traceback
from flask_cors import CORS
from dotenv import load_dotenv
import time
import shutil
import logging

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Ensure 'processed' directory exists
os.makedirs('processed', exist_ok=True)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/process', methods=['POST'])
def process_image():
    image_path = None
    output_path = None
    process_id = str(int(time.time()))
    
    try:
        # Get image data from POST request
        image_data = request.json.get('image')
        if not image_data or not image_data.startswith('data:image/'):
            return jsonify({'error': 'Invalid image data'}), 400
        
        # Extract mime type and base64 data
        mime_type = image_data.split(';')[0].split(':')[1]
        base64_data = image_data.split(',')[1]
        
        logging.info(f"Processing image with mime type: {mime_type}")
        
        # Create a temporary directory for this request
        temp_dir = tempfile.mkdtemp(prefix=f"watermark_process_{process_id}_")
        
        # Determine extension based on mime type
        ext = '.jpg'  # Default
        if 'png' in mime_type:
            ext = '.png'
        elif 'webp' in mime_type:
            ext = '.webp'
        elif 'gif' in mime_type:
            ext = '.gif'
        
        # Create a temporary file to save the image
        image_path = os.path.join(temp_dir, f"input{ext}")
        with open(image_path, 'wb') as temp_image:
            temp_image.write(base64.b64decode(base64_data))
        
        logging.info(f"Saved image to: {image_path}, size: {os.path.getsize(image_path)} bytes")
        
        # Get environment variables to pass to the subprocess
        env = os.environ.copy()
        
        # Run Python script with the image path as input
        logging.info("Starting py_watermark.py subprocess...")
        result = subprocess.run(
            ['python', 'py_watermark.py'],
            input=image_path,
            text=True,
            capture_output=True,
            env=env
        )
        
        # Log output for debugging
        logging.info(f"Script stdout: {result.stdout}")
        if result.stderr:
            logging.error(f"Script stderr: {result.stderr}")
        
        if result.returncode != 0:
            return jsonify({'error': 'Error processing image'}), 500
        
        output_path = result.stdout.strip()
        logging.info(f"Watermark removed, output saved to: {output_path}")
        
        # Return the processed image path as response
        with open(output_path, 'rb') as output_image:
            base64_output = base64.b64encode(output_image.read()).decode('utf-8')
            return jsonify({'success': True, 'imageData': f"data:image/{ext[1:]};base64,{base64_output}"})
    
    except Exception as e:
        logging.error("An error occurred", exc_info=True)
        return jsonify({'error': str(e)}), 500
    
    finally:
        # Clean up temporary files and directories
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    app.run()
