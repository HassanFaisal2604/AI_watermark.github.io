import base64
import os
import mimetypes
import sys
import tempfile
import time
import random
from PIL import Image
from google import genai
from google.genai import types
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
        
        # Always convert to PNG for consistency
        print("Converting image to PNG for consistent handling...")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_file.close()
        
        # Save as PNG
        img.save(temp_file.name, 'PNG')
        print(f"Converted image saved to: {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        print(f"Error validating image: {str(e)}")
        print(traceback.format_exc())
        raise

def generate(api_key):
    temp_file_path = None
    try:
        print(f"Using API key: {api_key[:5]}...")  # Print first few chars to confirm loading
        
        # Validate and convert the image
        temp_file_path = validate_and_convert_image(user_infile)
        
        # Initialize client with API key
        print("Initializing Gemini client...")
        client = genai.Client(api_key=api_key)
        
        print(f"Uploading file: {temp_file_path}")
        files = [
            client.files.upload(file=temp_file_path),
        ]
        print(f"File uploaded successfully with URI: {files[0].uri}")
        
        model = "gemini-2.0-flash-exp-image-generation"
        
        # Define multiple prompts to try in sequence
        prompts = [
            "Remove the watermark from this image completely. Reconstruct the underlying image perfectly.",
            
            "Using advanced image reconstruction, eliminate all watermarks, texts and logos from this image. Maintain the original image's quality, details and colors.",
            
            "Erase the watermark or text overlay from this image. Fill in the removed areas with content that matches the surrounding pixels perfectly.",
            
            "Clean this image by removing all watermarks, texts, logos or overlays. Keep everything else exactly as in the original.",
            
            "Please precisely identify and remove all watermarks, brand logos, and text overlays from this image. Reconstruct the areas underneath with pixel-perfect accuracy. Do not alter any other part of the image."
        ]
        
        # Try each prompt in sequence until success
        success = False
        response = None
        
        for attempt, prompt in enumerate(prompts, 1):
            if attempt > 1:
                print(f"Retrying with different prompt (attempt {attempt}/{len(prompts)})...")
                # Add a small delay between attempts
                time.sleep(2)
            
            print(f"Trying prompt: '{prompt}'")
            
            # Using the original config approach that works with your version
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["image", "text"],
                response_mime_type="text/plain",
            )
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(
                            file_uri=files[0].uri or "",
                            mime_type=files[0].mime_type or "",
                        ),
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            print(f"Sending request to model {model}...")
            
            try:
                # Try with streaming first
                chunks_received = 0
                for chunk in client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                ):
                    chunks_received += 1
                    if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                        print("Received empty chunk, continuing...")
                        continue
                    
                    part = chunk.candidates[0].content.parts[0]
                    if hasattr(part, "inline_data") and part.inline_data:
                        file_name = "watermark_removed"
                        inline_data = part.inline_data
                        print(f"Received inline data with mime type: {inline_data.mime_type}")
                        
                        file_extension = mimetypes.guess_extension(inline_data.mime_type)
                        if not file_extension:
                            file_extension = ".jpg"  # Default
                        
                        output_path = f"{file_name}{file_extension}"
                        print(f"Saving output to: {output_path}")
                        
                        if save_binary_file(output_path, inline_data.data):
                            success = True
                            print(f"File saved successfully to: {output_path}")
                            break  # Exit the chunk loop
                        else:
                            print("Failed to save the processed image")
                    elif hasattr(part, "text") and part.text:
                        print(f"Text response: {part.text}")
                    else:
                        print(f"Unknown response type: {type(part)}")
                
                print(f"Received {chunks_received} chunks in total")
                
                if success:
                    break  # Exit the prompt loop if successful
                
                # If streaming didn't work, try non-streaming as a fallback
                if not success and chunks_received == 0:
                    print("Streaming response empty, trying non-streaming API...")
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                        generation_config=generate_content_config,
                    )
                    
                    if response.candidates and response.candidates[0].content:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                file_name = "watermark_removed"
                                inline_data = part.inline_data
                                print(f"Received inline data with mime type: {inline_data.mime_type}")
                                
                                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                                if not file_extension:
                                    file_extension = ".jpg"  # Default
                                
                                output_path = f"{file_name}{file_extension}"
                                print(f"Saving output to: {output_path}")
                                
                                if save_binary_file(output_path, inline_data.data):
                                    success = True
                                    print(f"File saved successfully to: {output_path}")
                                    break  # Exit the part loop
                    
                    if success:
                        break  # Exit the prompt loop if successful
            
            except Exception as attempt_error:
                print(f"Error during attempt {attempt}: {str(attempt_error)}")
                print(traceback.format_exc())
                continue  # Try the next prompt
        
        if not success:
            print("Warning: No image data was received from the API")
            raise Exception("No image data received from the Gemini API after multiple attempts")
        
        return success
            
    except Exception as e:
        print(f"Error in generate function: {str(e)}")
        print(traceback.format_exc())
        raise
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"Temporary file removed: {temp_file_path}")
            except Exception as cleanup_error:
                print(f"Error removing temporary file: {str(cleanup_error)}")

if __name__ == "__main__":
    try:
        # Get API key from environment variable
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"Current working directory: {os.getcwd()}")
            print(f"Env vars available: {list(os.environ.keys())}")
            raise ValueError("API key not found. Please set GEMINI_API_KEY in the .env file.")
        
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