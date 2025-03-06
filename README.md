# Video Tagger

A Python script that uses Google's Gemini API to analyze videos and generate tags and descriptions.

## Setup

1. Create and activate a virtual environment:

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root directory with your Gemini API key:

   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

   To get a Gemini API key, visit: https://aistudio.google.com/app/apikey

## Usage

```
python video_tagger.py -v <video_path> [-o <output_file>] [-f <format>] [-w <wait_time>]
```

### Windows Batch Script

For Windows users, a convenient batch script is included:

1. Place your video files in a directory named `videos` in the same location as the script
2. Make sure your `.env` file is set up with your API key
3. Run `process_videos.bat` by double-clicking it
4. The script will process all videos and save the results to `results.csv`

### Arguments:

- `-v, --video`: Path to a video file or directory containing videos (required)
- `-o, --output`: Path to output file (optional, defaults to console output)
- `-f, --format`: Output format, either 'json', 'txt', or 'csv' (optional, defaults to 'json')
- `-w, --wait`: Wait time in seconds between processing videos (optional, defaults to 5 seconds)

### Examples:

Process all videos in a directory and place the response in a CSV file name results.csv

```
python video_tagger.py -v videos -o results.csv -f csv
```

Process a single video and print the results to the console:

```
python video_tagger.py -v path/to/video.mp4
```

Process all videos in a directory and save the results to a JSON file:

```
python video_tagger.py -v path/to/videos_directory -o results.json
```

Process a video and save the results in text format:

```
python video_tagger.py -v path/to/video.mp4 -o results.txt -f txt
```

Process all videos in a directory and save the results in a CSV file:

```
python video_tagger.py -v path/to/videos_directory -o results.csv -f csv
```

## Output Format

### JSON format:

```json
[
  {
    "filename": "video1.mp4",
    "response": "- Description: A concise description of the video (1 sentence, max 15 words).\n- Tags: [tag1, tag2, tag3]"
  },
  {
    "filename": "video2.mp4",
    "response": "- Description: Another concise video description.\n- Tags: [tag1, tag2, tag3, tag4]"
  }
]
```

### Text format:

```
File: video1.mp4
- Description: A concise description of the video (1 sentence, max 15 words).
- Tags: [tag1, tag2, tag3]
--------------------------------------------------------------------------------
File: video2.mp4
- Description: Another concise video description.
- Tags: [tag1, tag2, tag3, tag4]
--------------------------------------------------------------------------------
```

### CSV format:

```
Filename,Description,Tags
video1.mp4,"A concise description of the video (1 sentence, max 15 words)","[tag1, tag2, tag3]"
video2.mp4,"Another concise video description.","[tag1, tag2, tag3, tag4]"
```

## Prompt Information

The script uses the following prompt format with the Gemini API:

```
Given a short video description based on your observation of this video, generate:
1. A concise description (1 sentence, max 15 words) capturing the video's key visual and emotional elements.
2. A list of 2-5 tags (single words or short phrases) for filtering and context, focusing on appearance, emotion, and setting.

Example Input: "A man confidently speaking outdoors"
Example Output:
- Description: "A confident man speaking in an outdoor environment."
- Tags: ["man", "confident", "outdoor", "speaking"]
```

## How It Works

This script uses Google's Gemini File API to process videos, which offers several advantages:

1. **More reliable video processing**: The File API properly extracts frames from videos at 1 frame per second.
2. **Better handling of large files**: Supports videos up to 2GB in size.
3. **Audio processing**: The API also processes audio from the video at 1Kbps.
4. **Improved error handling**: Videos are processed on Google's servers before analysis.

The process for each video is:

1. Upload the video to the Gemini File API
2. Wait for Google's servers to process the video (may take a few minutes)
3. Once processing is complete, send the processed video to the Gemini model for analysis
4. Receive and parse the response

### Supported Video Formats

The script supports the following video formats:

- MP4 (.mp4)
- MPEG (.mpeg)
- QuickTime (.mov)
- AVI (.avi)
- Flash Video (.flv)
- MPEG Video (.mpg)
- WebM (.webm)
- Windows Media Video (.wmv)
- 3GPP (.3gp)

### Troubleshooting

If you encounter issues:

1. **Rate limiting errors**: Increase the wait time between videos using the `-w` parameter
2. **Timeout during processing**: Some videos may take longer to process. The script waits up to 10 minutes by default
3. **File upload failures**: Check your internet connection and ensure the file is valid
