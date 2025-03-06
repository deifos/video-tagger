import os
import sys
import argparse
import time
import random
import mimetypes
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

def setup_args():
    """Setup command line arguments."""
    parser = argparse.ArgumentParser(description='Generate tags and descriptions for video files using Google Gemini API.')
    parser.add_argument('-v', '--video', required=True, help='Path to the video file or directory of video files')
    parser.add_argument('-o', '--output', help='Path to output file (if not specified, prints to console)')
    parser.add_argument('-f', '--format', choices=['json', 'txt', 'csv'], default='json', help='Output format (default: json)')
    parser.add_argument('-w', '--wait', type=int, default=5, help='Initial wait time in seconds between video processing (default: 5)')
    parser.add_argument('-r', '--retry', action='store_true', help='Force retry processing of videos that failed previously')
    parser.add_argument('-s', '--specific', help='Process only a specific video file within a directory')
    return parser.parse_args()

def init_gemini_client():
    """Initialize the Gemini API client."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        print("Please create a .env file with your GEMINI_API_KEY.")
        sys.exit(1)
    
    genai.configure(api_key=api_key)
    return genai

def is_valid_video_file(file_path, min_size_bytes=10):
    """
    Check if the file is a valid video file that can be processed.
    
    Args:
        file_path: Path to the video file
        min_size_bytes: Minimum file size in bytes
    
    Returns:
        bool: True if the file is valid, False otherwise
    """
    file_path = Path(file_path)
    
    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        return False
    
    # Check file size (too small files are likely corrupted)
    if file_path.stat().st_size < min_size_bytes:
        return False
    
    # Check file extension
    video_extensions = ['.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp']
    if file_path.suffix.lower() not in video_extensions:
        return False
    
    # Try to determine mime type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type and not mime_type.startswith('video/'):
        return False
    
    return True

def upload_video_to_file_api(client, video_path, max_retries=3, base_delay=2):
    """
    Upload a video to the Gemini File API.
    
    Args:
        client: The Gemini API client
        video_path: Path to the video file
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        
    Returns:
        The file object if successful, None otherwise
    """
    retry_count = 0
    while retry_count <= max_retries:
        try:
            print(f"Uploading video to File API: {video_path}")
            file_obj = client.upload_file(path=str(video_path))
            print(f"Upload complete. File ID: {file_obj.name}")
            return file_obj
        except Exception as e:
            error_message = str(e)
            retry_count += 1
            
            if retry_count <= max_retries:
                delay = base_delay * (2 ** retry_count) + random.uniform(0, 1)
                print(f"Error uploading file: {error_message}")
                print(f"Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"Failed to upload file after {max_retries} attempts: {error_message}")
                return None
    
    return None

def wait_for_file_processing(client, file_obj, max_wait_time=600, check_interval=10):
    """
    Wait for a file to finish processing.
    
    Args:
        client: The Gemini API client
        file_obj: The file object
        max_wait_time: Maximum time to wait in seconds
        check_interval: Interval between checks in seconds
        
    Returns:
        The updated file object if processing is complete, None if failed or timed out
    """
    print(f"Waiting for video processing to complete...")
    start_time = time.time()
    
    while True:
        # Check if we've waited too long
        elapsed_time = time.time() - start_time
        if elapsed_time > max_wait_time:
            print(f"Timed out after waiting {elapsed_time:.1f} seconds for file processing")
            return None
        
        # Get the latest file status
        try:
            updated_file = client.get_file(file_obj.name)
            
            if updated_file.state.name == "ACTIVE":
                print(f"Video processing complete after {elapsed_time:.1f} seconds")
                return updated_file
            elif updated_file.state.name == "FAILED":
                print(f"Video processing failed with state: {updated_file.state.name}")
                return None
            else:
                # Still processing
                print(f"Still processing... ({elapsed_time:.1f}s elapsed)", end="\r")
                time.sleep(check_interval)
        except Exception as e:
            print(f"Error checking file status: {e}")
            return None

def analyze_video(client, video_path, max_retries=3):
    """
    Analyze the video and generate tags and description using the File API.
    
    This function uploads the video to the Gemini File API and processes the response.
    
    Args:
        client: The Gemini API client
        video_path: Path to the video file
        max_retries: Maximum number of retry attempts
    """
    video_path = Path(video_path)
    
    if not is_valid_video_file(video_path):
        print(f"Error: Invalid or unsupported video file: {video_path}")
        return {
            "filename": video_path.name,
            "error": "Invalid or unsupported video file"
        }
    
    # Get file size in MB for logging
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"Processing video: {video_path} ({file_size_mb:.2f} MB)")
    
    # Step 1: Upload the video to the File API
    file_obj = upload_video_to_file_api(client, video_path)
    if not file_obj:
        return {
            "filename": video_path.name,
            "error": "Failed to upload video to File API"
        }
    
    # Step 2: Wait for processing to complete
    processed_file = wait_for_file_processing(client, file_obj)
    if not processed_file:
        return {
            "filename": video_path.name,
            "error": "Video processing failed or timed out"
        }
    
    # Step 3: Generate content with the processed file
    prompt = """
    Given a short video description based on your observation of this video, generate:
    1. A concise description (1 sentence, max 15 words) capturing the video's key visual and emotional elements.
    2. A list of 2-5 tags (single words or short phrases) for filtering and context, focusing on appearance, emotion, and setting.

    Example Input: "A man confidently speaking outdoors"
    Example Output:
    - Description: "A confident man speaking in an outdoor environment."
    - Tags: ["man", "confident", "outdoor", "speaking"]

    Provide the output in this format:
    - Description: [your description]
    - Tags: [tag1, tag2, tag3, ...]
    """
    
    retry_count = 0
    while retry_count <= max_retries:
        try:
            # Configure the model
            model = client.GenerativeModel('gemini-2.0-pro-exp-02-05')
            
            # Create content parts using the file URI
            response = model.generate_content(
                contents=[
                    {
                        "parts": [
                            {"file_data": {"file_uri": processed_file.uri, "mime_type": "video/mp4"}},
                            {"text": prompt}
                        ]
                    }
                ]
            )
            
            if not response or not response.text or response.text.strip() == "":
                print(f"Warning: Empty response received for {video_path.name}")
                retry_count += 1
                if retry_count <= max_retries:
                    delay = 2 * (2 ** retry_count) + random.uniform(0, 1)
                    print(f"Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    return {
                        "filename": video_path.name,
                        "error": "Empty response received after multiple attempts"
                    }
            
            # Check if the response contains expected format
            text = response.text.strip()
            if not ("Description:" in text and "Tags:" in text):
                print(f"Warning: Response format incorrect for {video_path.name}")
                print(f"Response was: {text[:100]}...")
                
                # Try to fix common formatting issues
                if "description" in text.lower() and "tags" in text.lower():
                    # Try to reformat the response
                    lines = text.split('\n')
                    formatted_text = ""
                    for line in lines:
                        line = line.strip()
                        if line.lower().startswith("description:") or "description:" in line.lower():
                            formatted_text += "- Description:" + line.split("description:", 1)[1].strip() + "\n"
                        elif line.lower().startswith("tags:") or "tags:" in line.lower():
                            formatted_text += "- Tags:" + line.split("tags:", 1)[1].strip()
                    
                    if formatted_text:
                        print(f"Successfully reformatted response for {video_path.name}")
                        text = formatted_text
            
            print(f"Successfully generated description and tags for {video_path.name}")
            return {
                "filename": video_path.name,
                "response": text
            }
        except Exception as e:
            error_message = str(e)
            retry_count += 1
            
            if retry_count <= max_retries:
                delay = 2 * (2 ** retry_count) + random.uniform(0, 1)
                print(f"Error generating content: {error_message}")
                print(f"Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"Failed to generate content after {max_retries} attempts: {error_message}")
                return {
                    "filename": video_path.name,
                    "error": error_message
                }
    
    return {
        "filename": video_path.name,
        "error": "Maximum retry attempts exceeded"
    }

def process_videos(client, video_path, wait_time=5, force_retry=False, specific_file=None):
    """Process single video or directory of videos."""
    path = Path(video_path)
    results = []
    
    if path.is_file():
        # Process single video file
        result = analyze_video(client, path)
        if result:
            results.append(result)
    elif path.is_dir():
        # Process all video files in directory
        video_extensions = ['.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp']
        video_files = []
        
        # First collect all video files
        for file_path in path.glob('**/*'):
            if file_path.suffix.lower() in video_extensions:
                # If specific file is specified, only include that file
                if specific_file and file_path.name != specific_file:
                    continue
                video_files.append(file_path)
        
        print(f"Found {len(video_files)} video files to process.")
        
        # Check for previous results if not forcing retry
        previous_results = []
        previous_processed = set()
        
        if not force_retry and Path("results.csv").exists():
            try:
                import csv
                print("Found previous results.csv file. Checking for already processed videos...")
                with open("results.csv", "r") as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        if len(row) >= 3 and row[0]:  # Check if filename exists
                            filename = row[0]
                            description = row[1]
                            tags = row[2]
                            
                            # Skip videos with empty results unless force_retry is True
                            if description and tags:
                                previous_processed.add(filename)
                                previous_results.append({
                                    "filename": filename,
                                    "response": f"- Description: {description}\n- Tags: {tags}"
                                })
                                print(f"Skipping already processed video: {filename}")
                
                # Remove already processed files from the list unless force_retry is True
                if previous_processed:
                    video_files = [f for f in video_files if f.name not in previous_processed]
                    print(f"After filtering, {len(video_files)} videos remain to be processed.")
            except Exception as e:
                print(f"Error reading previous results: {e}")
        
        # Process each video with a delay between requests to avoid rate limiting
        for i, file_path in enumerate(video_files):
            result = analyze_video(client, file_path)
            if result:
                results.append(result)
                
            # Add a delay between videos if not the last file
            if i < len(video_files) - 1:
                delay = wait_time + random.uniform(1, 3)  # Random delay with the specified base time
                print(f"Waiting {delay:.2f} seconds before processing the next video...")
                time.sleep(delay)
        
        # Add previously processed results to the new results
        results.extend(previous_results)
    else:
        print(f"Error: Path not found: {video_path}")
    
    return results

def format_output(results, format_type='json'):
    """Format the results based on the specified format."""
    if format_type == 'json':
        import json
        return json.dumps(results, indent=2)
    elif format_type == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Filename', 'Description', 'Tags'])
        
        # Write data rows
        for result in results:
            if 'error' in result:
                # For errors, include the error message in the description column
                writer.writerow([result['filename'], f"ERROR: {result['error']}", ""])
                print(f"Note: Writing error for {result['filename']}: {result['error']}")
            else:
                # Parse the response to extract description and tags
                response_lines = result['response'].strip().split('\n')
                description = ''
                tags = ''
                
                # Debug output
                print(f"Processing CSV output for {result['filename']}")
                print(f"Response has {len(response_lines)} lines")
                
                for line in response_lines:
                    line = line.strip()
                    if line.startswith('- Description:'):
                        description = line.replace('- Description:', '').strip()
                        print(f"Found description: {description[:30]}...")
                    elif line.startswith('- Tags:'):
                        tags = line.replace('- Tags:', '').strip()
                        print(f"Found tags: {tags[:30]}...")
                
                if not description and not tags:
                    print(f"Warning: Could not find description or tags in response for {result['filename']}")
                    print(f"Response content: {result['response'][:100]}...")
                    # Try a less strict parsing approach
                    for line in response_lines:
                        line = line.strip().lower()
                        if 'description:' in line:
                            parts = line.split('description:', 1)
                            if len(parts) > 1:
                                description = parts[1].strip()
                                print(f"Found description with alternate parsing: {description[:30]}...")
                        elif 'tags:' in line:
                            parts = line.split('tags:', 1)
                            if len(parts) > 1:
                                tags = parts[1].strip()
                                print(f"Found tags with alternate parsing: {tags[:30]}...")
                
                writer.writerow([result['filename'], description, tags])
        
        return output.getvalue()
    else:  # txt format
        output = ""
        for result in results:
            output += f"File: {result['filename']}\n"
            if 'error' in result:
                output += f"Error: {result['error']}\n"
            else:
                output += f"{result['response']}\n"
            output += "-" * 80 + "\n"
        return output

def save_output(content, output_path):
    """Save the output to a file."""
    with open(output_path, 'w') as f:
        f.write(content)
    print(f"Results saved to {output_path}")

def main():
    args = setup_args()
    client = init_gemini_client()
    
    results = process_videos(client, args.video, args.wait, args.retry, args.specific)
    
    if not results:
        print("No results to display.")
        return
    
    formatted_output = format_output(results, args.format)
    
    if args.output:
        # If output is specified but no extension, add the format as extension
        output_path = args.output
        if not Path(output_path).suffix and args.format:
            output_path = f"{output_path}.{args.format}"
        save_output(formatted_output, output_path)
    else:
        print(formatted_output)

if __name__ == "__main__":
    main() 