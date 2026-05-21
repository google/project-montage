#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# Exit immediately if a command exits with a non-zero status
set -e

# Define source and destination directories relative to project root
SOURCE_DIR="../third_party/fonts"
DEST_DIR="assets/fonts"

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Starting font asset sync..."

# Safety Check: Verify that the source folder actually exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] Source directory '$SOURCE_DIR' does not exist. Cannot copy fonts." >&2
    exit 1
fi

# Ensure the parent assets folder exists
mkdir -p "assets"

# Execute copy operation
if command -v rsync &> /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Using rsync to sync fonts..."
    # The trailing slash on source avoids nesting fonts/ inside assets/fonts/
    rsync -av --delete "$SOURCE_DIR/" "$DEST_DIR"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] rsync not found. Falling back to cp..."
    # Clean up destination directory first to mimic a clean state sync
    rm -rf "$DEST_DIR"
    mkdir -p "$DEST_DIR"
    cp -r "$SOURCE_DIR/." "$DEST_DIR"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Successfully copied fonts to assets!"
