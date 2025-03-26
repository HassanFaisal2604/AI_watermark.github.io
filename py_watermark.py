import base64
import os
import mimetypes
import sys
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file with verbose output to debug issues
print("Loading environment variables...")
load_dotenv(verbose=True)

# Restore user-friendly prompt
user_infile = input("Enter the path of the image file: ")

def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)

def generate(api_key):
    print(f"Using API key: {api_key[:5]}...")  # Print first few chars to confirm loading
    # Initialize client with API key
    client = genai.Client(api_key=api_key)
    
    # Upload local image file - use Windows path format
    files = [
        client.files.upload(file=user_infile),
    ]
    
    model = "gemini-2.0-flash-exp-image-generation"
    
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=files[0].uri or "",  # Fix None check issue
                    mime_type=files[0].mime_type or "",  # Fix None check issue
                ),
                types.Part.from_text(text="Remove watermark"),
            ],
        ),
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="INSERT_INPUT_HERE"),
            ],
        ),
    ]
    
    generate_content_config = types.GenerateContentConfig(
        response_modalities=["image", "text"],
        response_mime_type="text/plain",
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,  # This might need conversion based on error
        config=generate_content_config,
    ):
        if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
            continue
        
        if hasattr(chunk.candidates[0].content.parts[0], "inline_data") and chunk.candidates[0].content.parts[0].inline_data:
            file_name = "watermark_removed"
            inline_data = chunk.candidates[0].content.parts[0].inline_data
            file_extension = mimetypes.guess_extension(inline_data.mime_type)  # Fixed typo here
            save_binary_file(f"{file_name}{file_extension}", inline_data.data)
            print(f"File of mime type {inline_data.mime_type} saved to: {file_name}{file_extension}")
        else:
            print(chunk.candidates[0].content.parts[0].text)

if __name__ == "__main__":
    # Get API key from environment variable
    api_key = os.getenv("MY_GENAI_KEY")
    if not api_key:
        # Check current directory for debugging
        print(f"Current working directory: {os.getcwd()}")
        print(f"Env vars available: {list(os.environ.keys())}")
        raise ValueError("API key not found. Please set MY_GENAI_KEY in the .env file.")
    generate(api_key)