"""
Upload NSE Analyzer project to GitHub via API (no git required)
Usage: python upload_to_github.py <YOUR_TOKEN>
"""
import sys
import os
import json
import base64
import requests

GITHUB_USERNAME = "suman972"
REPO_NAME = "nse-analyzer"
TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""

if not TOKEN:
    print("ERROR: Please provide your GitHub token as argument")
    print("Usage: python upload_to_github.py ghp_yourtoken")
    sys.exit(1)

PROJECT_DIR = r"C:\Users\suman_yrhfixt\Desktop\NSE-Option-Selling-Analyzer"

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Files to upload (skip large binaries, test files, cache)
SKIP_EXTENSIONS = {'.exe', '.pyc', '.pyd'}
SKIP_FILES = {
    'cloudflared.exe', 'cookies.txt', 'server_log.txt',
    'nse_home.html', 'oc_nifty.json', 'yt_extracted.json',
    'get_yt_info.py', 'config.yml'
}
SKIP_PREFIXES = ('test_', 'verify_', 'check_', 'patch_', 'apply_', 'scratch_')
SKIP_FOLDERS = {'__pycache__', 'uploads', 'sample_files'}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB limit per file

def should_skip(path, name, is_dir=False):
    if is_dir:
        return name in SKIP_FOLDERS
    if name in SKIP_FILES:
        return True
    if any(name.startswith(p) for p in SKIP_PREFIXES):
        return True
    if os.path.splitext(name)[1].lower() in SKIP_EXTENSIONS:
        return True
    if os.path.getsize(path) > MAX_FILE_SIZE:
        print(f"  SKIP (too large): {name}")
        return True
    return False

def get_all_files():
    files = []
    for root, dirs, filenames in os.walk(PROJECT_DIR):
        # Filter out skipped folders
        dirs[:] = [d for d in dirs if not should_skip(os.path.join(root, d), d, is_dir=True)]
        for fname in filenames:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, PROJECT_DIR).replace('\\', '/')
            if not should_skip(fpath, fname):
                files.append((fpath, rel_path))
    return files

def create_repo():
    url = "https://api.github.com/user/repos"
    data = {
        "name": REPO_NAME,
        "description": "NSE Institutional Derivatives & Option Selling Intelligence System",
        "private": False,
        "auto_init": False
    }
    r = requests.post(url, headers=HEADERS, json=data)
    if r.status_code == 201:
        print(f"Created repo: https://github.com/{GITHUB_USERNAME}/{REPO_NAME}")
        return True
    elif r.status_code == 422:
        print(f"Repo already exists: https://github.com/{GITHUB_USERNAME}/{REPO_NAME}")
        return True
    else:
        print(f"Failed to create repo: {r.status_code} {r.text}")
        return False

def upload_file(fpath, rel_path):
    with open(fpath, 'rb') as f:
        content = base64.b64encode(f.read()).decode('utf-8')

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{rel_path}"

    # Check if file already exists (to get SHA for update)
    r = requests.get(url, headers=HEADERS)
    sha = r.json().get('sha') if r.status_code == 200 else None

    data = {
        "message": f"Add {rel_path}",
        "content": content
    }
    if sha:
        data["sha"] = sha

    r = requests.put(url, headers=HEADERS, json=data)
    if r.status_code in (200, 201):
        return True
    else:
        print(f"  FAILED: {rel_path} -> {r.status_code}: {r.json().get('message','')}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print(f"  Uploading NSE Analyzer to GitHub/{GITHUB_USERNAME}/{REPO_NAME}")
    print("=" * 60)

    # Step 1: Create repo
    if not create_repo():
        sys.exit(1)

    # Step 2: Get all files
    files = get_all_files()
    print(f"\nFound {len(files)} files to upload\n")

    # Step 3: Upload each file
    success = 0
    failed = 0
    for i, (fpath, rel_path) in enumerate(files):
        print(f"[{i+1}/{len(files)}] Uploading: {rel_path}")
        if upload_file(fpath, rel_path):
            success += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"  DONE! {success} files uploaded, {failed} failed")
    print(f"  GitHub URL: https://github.com/{GITHUB_USERNAME}/{REPO_NAME}")
    print("=" * 60)
