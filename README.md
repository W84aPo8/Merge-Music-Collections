# Merge Music (or any other file) Collections and avoid duplicate Files

# How it works now:

## 1. Index target directory
Calculate MD5 of all existing files

## 2. Scan source directory
Calculate MD5 of all source files

## 3. Comparison
If MD5(source) already exists in MD5 index(target) → File already exists → Skip

## 4. Copy
Only if MD5 does not yet exist in the destination
