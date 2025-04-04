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

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Load environment variables
print("Server loading environment variables...")
load_dotenv(verbose=True)

# Check for API key at startup
api_key = os.getenv("MY_GENAI_KEY")
if not api_key:
    print("WARNING: MY_GENAI_KEY environment variable not found!")
    print(f"Available environment variables: {list(os.environ.keys())}")
else:
    print(f"API key found with length: {len(api_key)}")

# Ensure processed directory exists
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
        
        print(f"Processing image with mime type: {mime_type}")
        
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
        
        print(f"Saved image to: {image_path}, size: {os.path.getsize(image_path)} bytes")
        
        # Get environment variables to pass to the subprocess
        env = os.environ.copy()
        
        # Check if API key is available
        if "MY_GENAI_KEY" not in env:
            print("WARNING: MY_GENAI_KEY not in environment, trying to set it")
            api_key = os.getenv("MY_GENAI_KEY")
            if api_key:
                env["MY_GENAI_KEY"] = api_key
                print("Set MY_GENAI_KEY in subprocess environment")
            else:
                print("Failed to get MY_GENAI_KEY from os.getenv")
        
        # Run Python script with the image path as input
        print(f"Starting py_watermark.py subprocess...")
        process = subprocess.Popen(
            ['python', 'py_watermark.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Send the image path to the script's input
        stdout, stderr = process.communicate(input=image_path)
        
        # Print output for debugging
        print(f"Script stdout: {stdout}")
        if stderr:
            print(f"Script stderr: {stderr}")
        
        if process.returncode != 0:
            return jsonify({'error': 'Error processing image'}), 500
        
        output_path = stdout.strip()
        print(f"Watermark removed, output saved to: {output_path}")
        
        # Return the processed image path as response
        with open(output_path, 'rb') as output_image:
            base64_output = base64.b64encode(output_image.read()).decode('utf-8')
            return jsonify({'success': True, 'imageData': f"data:image/{ext[1:]};base64,{base64_output}"})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
    finally:
        # Clean up temporary files and directories
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    app.run(port=5000)