#!/bin/bash
echo "=== Fixing imports in all Python files ==="

# Find and fix all Python files
find app -name "*.py" -type f | while read file; do
    echo "Fixing: $file"
    # Remove 'app.' prefix from imports
    sed -i 's/from app\./from /g' "$file"
    sed -i 's/import app\./import /g' "$file"
    # Fix string references
    sed -i "s/'app\./'/g" "$file"
    sed -i 's/"app\./"/g' "$file"
done

echo "✅ All imports fixed"
