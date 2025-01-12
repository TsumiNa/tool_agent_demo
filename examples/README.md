# Tool Agent Demo Examples

This directory contains example implementations demonstrating various capabilities of the Tool Agent framework.

## Examples Overview

### Basic Example (basic_example.py)
A simple example showing the basic concepts of tools and workflows.

### Advanced Example (advanced_example.py)
Demonstrates error handling, data storage, and basic workflow combinations.

### Real-World Example (real_world_example.py)
A business intelligence system that demonstrates:
- Time-consuming data processing tasks
- Complex workflow combinations
- File I/O operations
- Data analysis and reporting
- Error handling and recovery

### Web Scraping Example (web_scraping_example.py)
Shows how to handle web interactions and parallel processing:
- Asynchronous HTTP requests
- HTML parsing and analysis
- Parallel website processing
- Caching mechanism
- Result aggregation

### Image Processing Example (image_processing_example.py)
Demonstrates CPU-intensive operations and binary data handling:
- Image loading and saving
- Image analysis and enhancement
- Parallel batch processing
- Progress tracking
- Result reporting

## Requirements

### Core Dependencies
```bash
# Install with uv
uv add tool-agent-demo
```

### Example-specific Dependencies

For web_scraping_example.py:
```bash
uv add aiohttp beautifulsoup4
```

For image_processing_example.py:
```bash
uv add pillow numpy
```

## Usage

### Running the Examples

1. Basic Example:
```bash
python examples/basic_example.py
```

2. Advanced Example:
```bash
python examples/advanced_example.py
```

3. Real-World Example:
```bash
python examples/real_world_example.py
```

4. Web Scraping Example:
```bash
python examples/web_scraping_example.py
```

5. Image Processing Example:
```bash
# First, create some sample images
mkdir -p images
# Add some .jpg files to the images directory
python examples/image_processing_example.py
```

## Key Features Demonstrated

### Asynchronous Operations
- Web requests (web_scraping_example.py)
- Parallel processing (image_processing_example.py)
- Workflow execution (real_world_example.py)

### Error Handling
- Network errors (web_scraping_example.py)
- File I/O errors (real_world_example.py)
- Processing errors (image_processing_example.py)

### Complex Workflows
- Multi-step data processing (real_world_example.py)
- Parallel task execution (web_scraping_example.py)
- Conditional processing (image_processing_example.py)

### Data Management
- File I/O operations
- Caching mechanisms
- Result aggregation
- Progress tracking

## Best Practices Shown

1. **Error Handling**
   - Proper use of Result type for error propagation
   - Graceful error recovery
   - User-friendly error messages

2. **Resource Management**
   - Proper cleanup of resources
   - Efficient use of memory
   - Cache management

3. **Code Organization**
   - Clear separation of tools and workflows
   - Logical grouping of related functionality
   - Comprehensive documentation

4. **Performance Optimization**
   - Parallel processing where appropriate
   - Caching of expensive operations
   - Efficient data structures

5. **User Experience**
   - Progress reporting
   - Clear output formatting
   - Helpful error messages

## Contributing

Feel free to add more examples or improve existing ones. When contributing:

1. Follow the existing code style
2. Add comprehensive documentation
3. Include error handling
4. Add appropriate tests
5. Update this README.md with any new dependencies or usage instructions
