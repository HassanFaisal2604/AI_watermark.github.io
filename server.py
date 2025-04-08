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
import glob

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Load environment variables
print("Server loading environment variables...")
load_dotenv(verbose=True)

# Check for API key at startup
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY environment variable not found!")
    print(f"Available environment variables: {list(os.environ.keys())}")
else:
    print(f"API key found with length: {len(api_key)}")

# Ensure processed directory exists
os.makedirs('processed', exist_ok=True)

def cleanup_old_files():
    """Clean up old temporary files and processed images"""
    try:
        # Clean up old temporary files
        for file in glob.glob('watermark_removed.*'):
            try:
                os.remove(file)
                print(f"Cleaned up old file: {file}")
            except Exception as e:
                print(f"Error cleaning up {file}: {str(e)}")
        
        # Clean up old processed files
        for file in glob.glob('processed/*'):
            try:
                if os.path.isfile(file):
                    os.remove(file)
                    print(f"Cleaned up processed file: {file}")
            except Exception as e:
                print(f"Error cleaning up {file}: {str(e)}")
    except Exception as e:
        print(f"Error in cleanup_old_files: {str(e)}")

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/process', methods=['POST'])
def process_image():
    image_path = None
    output_path = None
    temp_dir = None
    process_id = str(int(time.time()))
    
    try:
        # Clean up old files before processing
        cleanup_old_files()
        
        # Get image data from POST request
        if not request.json:
            return jsonify({'error': 'No JSON data received'}), 400
            
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
        if "GEMINI_API_KEY" not in env:
            print("WARNING: GEMINI_API_KEY not in environment, trying to set it")
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                env["GEMINI_API_KEY"] = api_key
                print("Set GEMINI_API_KEY in subprocess environment")
            else:
                print("Failed to get GEMINI_API_KEY from os.getenv")
        
        # Check if py_watermark.py exists
        if not os.path.exists('py_watermark.py'):
            return jsonify({'error': 'Processing script (py_watermark.py) not found'}), 500
        
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
        expected_outputs = []
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            expected_path = f"watermark_removed{ext}"
            expected_outputs.append(expected_path)
            if os.path.exists(expected_path):
                output_path = expected_path
                break
        
        if not output_path:
            return jsonify({
                'error': 'Output file not found after processing',
                'stdout': stdout,
                'stderr': stderr,
                'files_in_dir': os.listdir('.'),
                'expected_files': expected_outputs
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
        
        # Move the processed file to the processed directory
        processed_path = os.path.join('processed', f"{process_id}{os.path.splitext(output_path)[1]}")
        shutil.move(output_path, processed_path)
        output_path = processed_path
        
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
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"Removed temporary directory: {temp_dir}")
        except Exception as cleanup_error:
            print(f"Error during cleanup: {str(cleanup_error)}")

@app.route('/download/<path:filename>')
def download_file(filename):
    # Security: Ensure the filename is sanitized
    filename = os.path.basename(filename)
    if not os.path.exists(filename):
        return jsonify({'error': f'File not found: {filename}'}), 404
    return send_from_directory('.', filename, as_attachment=True)

if __name__ == '__main__':
    # Get port from environment variable (for Railway deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # In production, disable debug mode
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', debug=debug_mode, port=port)