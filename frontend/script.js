// Set the API URL based on environment
const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ?
    'http://localhost:5000' :
    'https://your-railway-app-url.railway.app'; // Replace with your actual Railway URL when deployed

document.addEventListener('DOMContentLoaded', () => {
    const imageInput = document.getElementById('imageInput');
    const originalImage = document.getElementById('originalImage');
    const processedImage = document.getElementById('processedImage');
    const downloadLink = document.getElementById('downloadLink');
    const loading = document.getElementById('loading');
    const errorMessage = document.getElementById('errorMessage');

    imageInput.addEventListener('change', handleImageUpload);

    function handleImageUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Display original image
        const reader = new FileReader();
        reader.onload = function(e) {
            originalImage.src = e.target.result;
            originalImage.style.display = 'block';

            // Clear previous results
            processedImage.style.display = 'none';
            downloadLink.style.display = 'none';
            errorMessage.style.display = 'none';

            // Show loading indicator
            loading.style.display = 'flex';

            // Send to API for processing
            processImage(e.target.result);
        };
        reader.readAsDataURL(file);
    }

    async function processImage(imageData) {
        try {
            const response = await fetch(`${API_URL}/process`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ image: imageData })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Failed to process image');
            }

            // Display processed image
            processedImage.src = result.imageData;
            processedImage.style.display = 'block';

            // Set up download link
            downloadLink.href = `${API_URL}/download/${result.outputPath}`;
            downloadLink.style.display = 'inline-block';

            // Hide loading indicator
            loading.style.display = 'none';

        } catch (error) {
            console.error('Error:', error);
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
            loading.style.display = 'none';
        }
    }
});