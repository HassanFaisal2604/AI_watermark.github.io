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
            return jsonify({
                'error': f'Python script error (code {process.returncode})', 
                'stdout': stdout,
                'stderr': stderr
            }), 500
        
        # Check if the watermark_removed file was created
        output_path = None
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            if os.path.exists(f"watermark_removed{ext}"):
                output_path = f"watermark_removed{ext}"
                break
        
        if not output_path:
            return jsonify({
                'error': 'Output file not found after processing',
                'stdout': stdout,
                'stderr': stderr,
                'files_in_dir': os.listdir('.')
            }), 500
        
        print(f"Found processed image at: {output_path}")
        
        # Check if file is readable
        if not os.access(output_path, os.R_OK):
            return jsonify({'error': 'Cannot read output file (permission denied)'}), 500
        
        # Get file size for verification
        file_size = os.path.getsize(output_path)
        print(f"Output file size: {file_size} bytes")
        
        if file_size == 0:
            return jsonify({'error': 'Output file is empty'}), 500
        
        # Determine correct mime type based on file extension
        mime_type = 'image/jpeg'  # Default
        if output_path.endswith('.png'):
            mime_type = 'image/png'
        elif output_path.endswith('.webp'):
            mime_type = 'image/webp'
        elif output_path.endswith('.gif'):
            mime_type = 'image/gif'
        
        # Return the path and also base64 data for direct display
        with open(output_path, 'rb') as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        # Return both path and data with correct mime type
        return jsonify({
            'success': True, 
            'outputPath': output_path,
            'imageData': f"data:{mime_type};base64,{img_data}"
        })
    
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"Error: {str(e)}\n{error_traceback}")
        return jsonify({'error': str(e), 'traceback': error_traceback}), 500
    
    finally:
        # Clean up temporary files
        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
                print(f"Removed temporary input file: {image_path}")
            
            # Remove temporary directory if it exists
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"Removed temporary directory: {temp_dir}")
        except Exception as cleanup_error:
            print(f"Error during cleanup: {str(cleanup_error)}")

# Add a specific endpoint for downloading the file
@app.route('/download/<path:filename>')
def download_file(filename):
    # Security: Ensure the filename is sanitized
    filename = os.path.basename(filename)
    if not os.path.exists(filename):
        return jsonify({'error': f'File not found: {filename}'}), 404
    return send_from_directory('.', filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}...")
    app.run(debug=True, host="0.0.0.0", port=port)
