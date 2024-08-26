"""
Sourced from https://github.com/johntday/notion-load/blob/main/notion_load/load.py
"""

import argparse
import traceback

from dotenv import load_dotenv

from utils.load_pgvector import load_pgvector


def cli():
    # https://realpython.com/command-line-interfaces-python-argparse/#handling-how-your-cli-apps-execution-terminates
    parser = argparse.ArgumentParser(prog="load.py", description="Load data into vector database")
    parser.add_argument("source",
                        choices=['notion'],
                        help="source can only be 'notion'")
    parser.add_argument("target",
                        choices=['pgvector'],
                        help="target can only be 'pgvector'")
    parser.add_argument("-v", "--verbose",
                        help="verbose logging",
                        action="store_true")
    parser.add_argument("-r", "--reset",
                        help="this will reset collection before loading",
                        action="store_true")

    args = parser.parse_args()

    # print(args)

    if args.verbose:
        print("  - verbose on")
    else:
        print("  - verbose off")

    print(f"  - fetching documents from: {args.source}")
    print(f"  - loading processed documents into: {args.target}")
    print(f"  - reset collection before loading: {args.reset}")
    print()
    return args


if __name__ == '__main__':
    load_dotenv()

    args = cli()

    try:
        if args.target == 'pgvector':
            load_pgvector(args)
        elif args.target == 'local':
            print("Loading locally not implemented yet")
            exit(1)
        else:
            print(args)
            print(f"Invalid target: {args.target}")

    except Exception as e:
        print("LOAD FAILED")
        #print(e)
        traceback.print_exc()
        exit(1)