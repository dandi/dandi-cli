import os
import re


def rename_files_in_dist():
    dist_dir = 'dist'
    for filename in os.listdir(dist_dir):
        # Define the pattern to match filenames in the dist directory
        # This pattern is looking for filenames that start with any character
        # sequence, followed by a version number (PEP 440 compliant), and ending
        # with a file extension (.tar.gz, .whl, etc.)
        pattern = r'(.*?)(\d+\.\d+(\.\d+)?(\.post\d+)?(\.dev\d+)?)(.*?)$'
        match = re.match(pattern, filename)

        if match:
            # Break the filename into parts
            prefix = match.group(1)  # The part before the version number
            version = match.group(2)  # The version number
            suffix = match.group(6)  # The file extension and any other suffix

            # Construct the new filename with the .linc suffix before the file extension
            new_filename = f"{prefix}{version}.post2{suffix}"
            new_path = os.path.join(dist_dir, new_filename)

            # Construct the old file path
            old_path = os.path.join(dist_dir, filename)

            # Rename the file
            os.rename(old_path, new_path)
            print(f"Renamed '{filename}' to '{new_filename}'")

        else:
            # If the filename doesn't match the pattern, print a message
            print(f"Filename '{filename}' does not match the expected pattern. Skipping.")


if __name__ == "__main__":
    rename_files_in_dist()
