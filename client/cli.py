
import argparse, requests, sys, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="Path to audio file")
    ap.add_argument("--url", default="http://localhost:8000/transcribe")
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        files = {"file": (os.path.basename(args.file), f, "application/octet-stream")}
        r = requests.post(args.url, files=files, timeout=120)
        r.raise_for_status()
        print(r.json())

if __name__ == "__main__":
    main()
