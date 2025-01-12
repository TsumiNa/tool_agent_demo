import asyncio
import time
import io
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np
from tool_agent_demo import Agent, Result


class ImageProcessingAgent(Agent):
    def __init__(self):
        super().__init__()
        self.image_dir = Path("images")
        self.image_dir.mkdir(exist_ok=True)
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)

    @Agent.tool
    def load_image(self, path: str) -> Image.Image:
        """Load an image from file"""
        time.sleep(0.2)  # Simulate I/O delay
        return Image.open(path)

    @Agent.tool
    def save_image(self, image: Image.Image, filename: str) -> str:
        """Save an image to file"""
        time.sleep(0.2)  # Simulate I/O delay
        filepath = self.results_dir / filename
        image.save(filepath)
        return str(filepath)

    @Agent.tool
    def analyze_image(self, image: Image.Image) -> Dict:
        """Analyze image properties"""
        time.sleep(0.5)  # Simulate processing time

        # Convert to numpy array for analysis
        img_array = np.array(image)

        # Calculate basic statistics
        if len(img_array.shape) == 3:  # Color image
            brightness = np.mean(img_array)
            contrast = np.std(img_array)
            color_means = [float(np.mean(img_array[:, :, i]))
                           for i in range(3)]
        else:  # Grayscale image
            brightness = float(np.mean(img_array))
            contrast = float(np.std(img_array))
            color_means = [brightness]

        return {
            "size": image.size,
            "mode": image.mode,
            "format": image.format,
            "brightness": float(brightness),
            "contrast": float(contrast),
            "color_means": color_means,
            "aspect_ratio": image.size[0] / image.size[1]
        }

    @Agent.tool
    def enhance_image(self, image: Image.Image,
                      brightness: float = 1.0,
                      contrast: float = 1.0,
                      sharpness: float = 1.0) -> Image.Image:
        """Apply various enhancements to an image"""
        time.sleep(0.3)  # Simulate processing time

        # Apply enhancements sequentially
        if brightness != 1.0:
            image = ImageEnhance.Brightness(image).enhance(brightness)
        if contrast != 1.0:
            image = ImageEnhance.Contrast(image).enhance(contrast)
        if sharpness != 1.0:
            image = ImageEnhance.Sharpness(image).enhance(sharpness)

        return image

    @Agent.tool
    def apply_filters(self, image: Image.Image,
                      filters: List[str]) -> Image.Image:
        """Apply a sequence of filters to an image"""
        time.sleep(0.4)  # Simulate processing time

        filter_map = {
            "blur": ImageFilter.BLUR,
            "sharpen": ImageFilter.SHARPEN,
            "edge_enhance": ImageFilter.EDGE_ENHANCE,
            "emboss": ImageFilter.EMBOSS,
            "smooth": ImageFilter.SMOOTH
        }

        result = image
        for filter_name in filters:
            if filter_name in filter_map:
                result = result.filter(filter_map[filter_name])

        return result

    @Agent.tool
    def resize_image(self, image: Image.Image,
                     max_size: Tuple[int, int]) -> Image.Image:
        """Resize image while maintaining aspect ratio"""
        time.sleep(0.3)  # Simulate processing time

        # Calculate new size maintaining aspect ratio
        ratio = min(max_size[0] / image.size[0],
                    max_size[1] / image.size[1])
        new_size = tuple(int(dim * ratio) for dim in image.size)

        return image.resize(new_size, Image.Resampling.LANCZOS)

    @Agent.workflow
    def process_single_image(self, input_path: str) -> Result:
        """Workflow to process a single image with enhancements"""
        try:
            # Load the image
            image_result = self.load_image(input_path)
            if image_result.is_err():
                return image_result
            image = image_result.unwrap()

            # Analyze original image
            analysis_result = self.analyze_image(image)
            if analysis_result.is_err():
                return analysis_result
            analysis = analysis_result.unwrap()

            # Determine enhancements based on analysis
            brightness_factor = 1.2 if analysis["brightness"] < 128 else 0.8
            contrast_factor = 1.3 if analysis["contrast"] < 50 else 0.9

            # Apply enhancements
            enhanced_result = self.enhance_image(
                image,
                brightness=brightness_factor,
                contrast=contrast_factor,
                sharpness=1.2
            )
            if enhanced_result.is_err():
                return enhanced_result
            enhanced = enhanced_result.unwrap()

            # Apply filters
            filtered_result = self.apply_filters(
                enhanced,
                ["edge_enhance", "smooth"]
            )
            if filtered_result.is_err():
                return filtered_result
            filtered = filtered_result.unwrap()

            # Resize if too large
            final_image = filtered
            if max(image.size) > 1000:
                resized_result = self.resize_image(filtered, (1000, 1000))
                if resized_result.is_err():
                    return resized_result
                final_image = resized_result.unwrap()

            # Save the result
            output_path_result = self.save_image(
                final_image,
                f"enhanced_{Path(input_path).name}"
            )
            if output_path_result.is_err():
                return output_path_result
            output_path = output_path_result.unwrap()

            # Save analysis results
            final_analysis_result = self.analyze_image(final_image)
            if final_analysis_result.is_err():
                return final_analysis_result
            final_analysis = final_analysis_result.unwrap()

            # Create and yield the final results dictionary
            yield Result(value={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_analysis": analysis,
                "final_analysis": final_analysis
            })
        except Exception as e:
            return Result(error=str(e))

    @Agent.workflow
    async def batch_process_images(self, input_paths: List[str]) -> Result:
        """Process multiple images in parallel"""
        results = {}
        tasks = []

        # Create tasks for each image
        for path in input_paths:
            for result in self.process_single_image(path):
                if result.is_err():
                    results[path] = {"error": str(result.error)}
                else:
                    tasks.append(result)

        # Wait for all tasks to complete
        if tasks:
            completed = await asyncio.gather(*tasks)
            for path, result in zip(input_paths, completed):
                if isinstance(result, Exception):
                    results[path] = {"error": str(result)}
                else:
                    results[path] = result

        # Save batch results
        filepath = self.results_dir / "batch_results.json"
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)

        return Result(value=str(filepath))


def main():
    # Create the agent
    agent = ImageProcessingAgent()

    # Example image paths (you would need actual image files)
    image_paths = [
        "images/sample1.jpg",
        "images/sample2.jpg",
        "images/sample3.jpg"
    ]

    print("=== Single Image Processing ===")
    if len(image_paths) > 0:
        print(f"\nProcessing {image_paths[0]}...")
        start_time = time.time()
        # Process the image and collect all results
        results = []
        for result in agent.process_single_image(image_paths[0]):
            if result.is_err():
                print(f"Error: {result.error}")
                break
            results.append(result)

        # Get the final result (last one in the sequence)
        if results:
            final_result = results[-1]
            if final_result.is_ok():
                print(f"Processing completed in {
                      time.time() - start_time:.2f} seconds")
                result_value = final_result.value
                print("\nResults:")
                print(f"Input: {result_value['input_path']}")
                print(f"Output: {result_value['output_path']}")
                print("\nOriginal Analysis:")
                for k, v in result_value['original_analysis'].items():
                    print(f"  {k}: {v}")
                print("\nFinal Analysis:")
                for k, v in result_value['final_analysis'].items():
                    print(f"  {k}: {v}")

    print("\n=== Batch Image Processing ===")
    print(f"\nProcessing {len(image_paths)} images in parallel...")

    start_time = time.time()
    # Note: Batch processing is async, so we'll skip it for now
    print("\nSkipping batch processing (requires async support)")


if __name__ == "__main__":
    main()
