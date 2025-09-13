#!/bin/bash

# --- Script to split a video file based on a timestamp file and generate a transcription command ---

# Check if the correct number of arguments are provided.
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input_video.mp4> <timestamps.txt>"
    exit 1
fi

# Assign arguments to variables.
INPUT_VIDEO="$1"
TIMESTAMPS_FILE="$2"

# Check if the input video file exists.
if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Input video file not found at '$INPUT_VIDEO'"
    exit 1
fi

# Get the filename and extension from the original video.
FILENAME=$(basename -- "$INPUT_VIDEO" | sed 's/\.[^.]*$//')
EXTENSION="${INPUT_VIDEO##*.}"

# Get the absolute directory path of the timestamps file.
OUTPUT_DIR=$(dirname -- "$TIMESTAMPS_FILE")
ABS_OUTPUT_DIR=$(realpath "$OUTPUT_DIR")


# Initialize a counter and an array to store the paths of the output files.
LINE_NUM=1
output_files=()

# Read the timestamps file line by line.
while IFS= read -r line || [[ -n "$line" ]]; do
    # Trim whitespace from the line
    line=$(echo "$line" | xargs)

    # Skip empty lines or lines that do not match the hh:mm:ss - hh:mm:ss format.
    if ! [[ "$line" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}\ -\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
        echo "Skipping invalid line: $line"
        continue
    fi

    # Extract start and end times.
    START_TIME=$(echo "$line" | awk '{print $1}')
    END_TIME=$(echo "$line" | awk '{print $3}')

    # Construct the full path for the output file.
    OUTPUT_FILE="${ABS_OUTPUT_DIR}/${FILENAME}_${LINE_NUM}.${EXTENSION}"

    echo "--------------------------------------------------"
    echo "Processing Segment $LINE_NUM..."
    echo "Output file: $OUTPUT_FILE"
    
    # Use ffmpeg to split the video.
    # -nostdin prevents ffmpeg from consuming input meant for the script.
    ffmpeg -y -nostdin -v quiet -stats -i "$INPUT_VIDEO" -ss "$START_TIME" -to "$END_TIME" -c copy "$OUTPUT_FILE"

    echo "Segment $LINE_NUM created successfully."
    
    # Add the path of the newly created file to our array.
    output_files+=("$OUTPUT_FILE")

    # Increment the counter.
    ((LINE_NUM++))

done < "$TIMESTAMPS_FILE"

echo "--------------------------------------------------"

# Check if any files were created before generating the command.
if [ ${#output_files[@]} -gt 0 ]; then
    # Start building the transcription command.
    transcribe_command="source venv/bin/activate && python transcribe_video.py"

    # Add each output file path to the command, enclosed in quotes.
    for file in "${output_files[@]}"; do
        transcribe_command+=" \"$file\""
    done

    # Append the generated command to the timestamps file for easy access.
    echo -e "\n# Generated command for transcription:" >> "$TIMESTAMPS_FILE"
    echo "$transcribe_command" >> "$TIMESTAMPS_FILE"

    echo "✅ Automation complete. All video segments created."
    echo "✅ Transcription command has been appended to '$TIMESTAMPS_FILE'."
else
    echo "⚠️ No valid timestamps found or no video segments were created."
fi

