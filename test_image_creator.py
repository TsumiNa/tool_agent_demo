from PIL import Image, ImageDraw
import os

# Create images directory if it doesn't exist
os.makedirs('images', exist_ok=True)

# Create a sample image
img = Image.new('RGB', (400, 300), color='white')
draw = ImageDraw.Draw(img)

# Draw some shapes
draw.rectangle([50, 50, 350, 250], outline='blue', width=2)
draw.ellipse([100, 100, 300, 200], fill='red')

# Save the image
img.save('images/sample1.jpg')

print("Test image created successfully!")
