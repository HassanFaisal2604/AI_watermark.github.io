import base64
import os
import mimetypes
import sys
import tempfile
import time
import random
from PIL import Image, ImageFilter, ImageEnhance
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
import traceback

# Load environment variables from .env file with verbose output to debug issues
print("Loading environment variables...")
load_dotenv(verbose=True)

# Restore user-friendly prompt
user_infile = input("Enter the path of the image file: ")
print(f"Processing image: {user_infile}")

def save_binary_file(file_name, data):
    try:
        with open(file_name, "wb") as f:
            f.write(data)
        print(f"Successfully saved file to {file_name}")
        return True
    except Exception as e:
        print(f"Error saving file: {str(e)}")
        return False

def validate_and_convert_image(input_path):
    """Validate the image and convert it to a supported format if needed"""
    try:
        # Check if file exists
        if not os.path.exists(input_path):
            print(f"Error: File does not exist: {input_path}")
            raise FileNotFoundError(f"File not found: {input_path}")
        
        # Check file size
        file_size = os.path.getsize(input_path)
        print(f"Input file size: {file_size} bytes")
        if file_size == 0:
            raise ValueError(f"Input file is empty: {input_path}")
        
        # Try to open the image with PIL to verify it's valid
        print(f"Attempting to open image: {input_path}")
        img = Image.open(input_path)
        img.verify()  # Verify it's a valid image
        
        # Reopen the image after verification
        img = Image.open(input_path)
        print(f"Image format detected: {img.format}, size: {img.size}, mode: {img.mode}")
        
        return input_path  # Return original path since we don't need to convert
        
    except Exception as e:
        print(f"Error validating image: {str(e)}")
        print(traceback.format_exc())
        raise

def apply_basic_processing(image_path, output_path):
    """Apply basic image processing to simulate watermark removal"""
    try:
        print("Applying basic image processing...")
        img = Image.open(image_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Apply multiple processing techniques
        processed_img = img.copy()
        
        # 1. Slight sharpening to enhance details
        enhancer = ImageEnhance.Sharpness(processed_img)
        processed_img = enhancer.enhance(1.1)
        
        # 2. Slight contrast enhancement
        enhancer = ImageEnhance.Contrast(processed_img)
        processed_img = enhancer.enhance(1.05)
        
        # 3. Very light blur to smooth out potential artifacts
        processed_img = processed_img.filter(ImageFilter.GaussianBlur(radius=0.3))
        
        # Save the processed image
        processed_img.save(output_path, 'PNG', quality=95)
        print(f"Basic processing applied and saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error in basic processing: {str(e)}")
        return False

def try_gemini_analysis(api_key, image_path):
    """Try to use Gemini for image analysis (not generation)"""
    try:
        print("Attempting to analyze image with Gemini...")
        genai.configure(api_key=api_key)
        
        # Use the most efficient model for analysis
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Upload and analyze the image
        uploaded_file = genai.upload_file(image_path)
        
        # Wait for processing with timeout
        max_wait = 30  # seconds
        waited = 0
        while uploaded_file.state.name == "PROCESSING" and waited < max_wait:
            print("Waiting for file processing...")
            time.sleep(2)
            waited += 2
            uploaded_file = genai.get_file(uploaded_file.name)
        
        if uploaded_file.state.name == "FAILED":
            raise ValueError("File processing failed")
        
        # Simple analysis prompt
        prompt = "Analyze this image and describe any visible watermarks, text overlays, or logos."
        
        response = model.generate_content([uploaded_file, prompt])
        
        if response.text:
            print(f"Gemini analysis: {response.text}")
            
        # Clean up
        try:
            genai.delete_file(uploaded_file.name)
        except:
            pass
            
        return True
        
    except ResourceExhausted as e:
        print(f"API quota exceeded: {str(e)}")
        print("Falling back to basic processing...")
        return False
    except Exception as e:
        print(f"Error in Gemini analysis: {str(e)}")
        return False

def generate(api_key):
    temp_file_path = None
    try:
        print(f"Using API key: {api_key[:5]}...")
        
        # Validate the image
        validated_path = validate_and_convert_image(user_infile)
        
        # Try Gemini analysis first (this will fail gracefully if quota exceeded)
        gemini_success = try_gemini_analysis(api_key, validated_path)
        
        if gemini_success:
            print("Gemini analysis completed successfully.")
        else:
            print("Gemini analysis skipped due to quota limits or errors.")
        
        # Always apply basic processing as fallback
        output_path = "watermark_removed.png"
        
        print("\n" + "="*50)
        print("IMPORTANT NOTE:")
        print("True AI-powered watermark removal requires specialized models")
        print("that are not available through Gemini API.")
        print("This tool applies basic image enhancement as a demonstration.")
        print("For professional watermark removal, consider:")
        print("- Adobe Photoshop with Content-Aware Fill")
        print("- GIMP with Resynthesizer plugin")
        print("- Specialized watermark removal software")
        print("- Professional image editing services")
        print("="*50 + "\n")
        
        if apply_basic_processing(validated_path, output_path):
            print(f"Processing completed. Output saved to: {output_path}")
            return True
        else:
            print("Failed to process image")
            return False
            
    except Exception as e:
        print(f"Error in generate function: {str(e)}")
        print(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        # Get API key from environment variable
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"Current working directory: {os.getcwd()}")
            print("WARNING: GEMINI_API_KEY not found. Proceeding with basic processing only.")
            api_key = "dummy_key"  # Use dummy key for basic processing
        
        success = generate(api_key)
        
        # Verify output exists before exiting
        output_exists = False
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            if os.path.exists(f"watermark_removed{ext}"):
                output_exists = True
                print(f"Verified output file exists: watermark_removed{ext}")
                break
        
        if not output_exists:
            print("Warning: Output file not found after processing")
            sys.exit(1)
            
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)