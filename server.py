from flask import Flask, request, jsonify, send_from_directory
import subprocess
import os
import base64
import tempfile
import time
from flask_cors import CORS  # Add this import

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/process', methods=['POST'])
def process_image():
    try:
        # Get image data from POST request
        image_data = request.json.get('image')
        if not image_data or not image_data.startswith('data:image/'):
            return jsonify({'error': 'Invalid image data'}), 400
        
        # Extract base64 data after the comma
        base64_data = image_data.split(',')[1]
        
        # Create a temporary file to save the image
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_image:
            temp_image.write(base64.b64decode(base64_data))
            image_path = temp_image.name
        
        print(f"Saved image to: {image_path}")
        
        # Run Python script with the image path as input
        process = subprocess.Popen(
            ['python', 'py_watermark.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send the image path to the script's input
        stdout, stderr = process.communicate(input=image_path)
        
        if process.returncode != 0:
            # Clean up the temporary file
            if os.path.exists(image_path):
                os.remove(image_path)
            return jsonify({'error': f'Python script error: {stderr}'}), 500
        
        # Clean up the temporary file
        if os.path.exists(image_path):
            os.remove(image_path)
            
        # Check if the watermark_removed file was created
        output_path = None
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            if os.path.exists(f"watermark_removed{ext}"):
                output_path = f"watermark_removed{ext}"
                break
        
        if not output_path:
            return jsonify({'error': 'Output file not found'}), 500
        
        # Return the path to the processed image
        return jsonify({'success': True, 'outputPath': output_path})
    
    except Exception as e:
        # Ensure temp file cleanup even on errors
        if 'image_path' in locals() and os.path.exists(image_path):
            os.remove(image_path)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')