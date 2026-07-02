#!/usr/bin/env python3
"""Generate a random directory tree with files for testing Nexo transfers.

Usage:
    python scripts/gen_testdir.py ./test_data --depth 3 --files 20 --max-size 10M
    python scripts/gen_testdir.py ./test_data --depth 2 --files 50 --min-size 1K --max-size 100M
    python scripts/gen_testdir.py ./test_data --flat  --files 5 --max-size 1G
"""

import argparse
import os
import random
import string


def parse_size(s: str) -> int:
    s = s.strip().upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    if s[-1] in multipliers:
        return int(float(s[:-1]) * multipliers[s[-1]])
    return int(s)


def random_name(ext: bool = True) -> str:
    stem = "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 12)))
    if ext and random.random() < 0.7:
        stem += random.choice([".txt", ".bin", ".dat", ".log", ".jpg", ".png", ".py", ".json", ".csv", ".md"])
    return stem


def generate(
    root: str,
    depth: int,
    max_files: int,
    min_size: int,
    max_size: int,
    flat: bool = False,
):
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    created = 0

    dirs = [root]
    if not flat:
        # build directory tree
        level_dirs = [root]
        for _ in range(depth):
            next_dirs = []
            for d in level_dirs:
                if created >= max_files:
                    break
                for _ in range(random.randint(1, 4)):
                    sub = os.path.join(d, random_name(ext=False))
                    os.makedirs(sub, exist_ok=True)
                    next_dirs.append(sub)
            dirs.extend(next_dirs)
            level_dirs = next_dirs
            if not level_dirs:
                break

    # create files
    random.shuffle(dirs)
    file_count = 0
    total_bytes = 0

    print(f"Generating up to {max_files} files in {len(dirs)} directories...")

    for d in dirs:
        if file_count >= max_files:
            break
        n = random.randint(1, max(1, max_files // len(dirs) * 2))
        for _ in range(n):
            if file_count >= max_files:
                break
            fsize = random.randint(min_size, max_size)
            fpath = os.path.join(d, random_name())
            with open(fpath, "wb") as fh:
                # write in chunks to avoid huge memory usage
                remaining = fsize
                while remaining > 0:
                    chunk = min(remaining, 2**20)  # 1 MB chunks
                    fh.write(os.urandom(chunk))
                    remaining -= chunk
            file_count += 1
            total_bytes += fsize

            if file_count % 10 == 0 or file_count == max_files:
                print(f"  {file_count}/{max_files} files ({total_bytes / 2**20:.1f} MB)")

    print(f"\nDone: {file_count} files, {total_bytes / 2**20:.1f} MB in {root}")


def main():
    ap = argparse.ArgumentParser(description="Generate a random test directory tree")
    ap.add_argument("root", help="Output directory (will be created)")
    ap.add_argument("--depth", type=int, default=2, help="Directory nesting depth (default: 2)")
    ap.add_argument("--files", "-n", type=int, default=20, help="Number of files (default: 20)")
    ap.add_argument("--min-size", type=str, default="1K", help="Minimum file size (default: 1K)")
    ap.add_argument("--max-size", type=str, default="10M", help="Maximum file size (default: 10M)")
    ap.add_argument("--flat", action="store_true", help="Flat structure (no subdirectories)")
    args = ap.parse_args()

    generate(
        root=args.root,
        depth=args.depth,
        max_files=args.files,
        min_size=parse_size(args.min_size),
        max_size=parse_size(args.max_size),
        flat=args.flat,
    )


if __name__ == "__main__":
    main()
