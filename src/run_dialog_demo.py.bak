#!/usr/bin/env python3
"""
Stateful dialog demo is currently PAUSED for the deliverable.
This shim keeps the file discoverable and documents where to look next.
"""

import argparse, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stateful", action="store_true", help="Run the paused stateful demo (dev only)")
    args = ap.parse_args()

    if not args.stateful:
        print(
            "Stateful evals are currently paused.\n"
            "See docs/scenario_schema.md for the design.\n"
            "Re-enable later with a dedicated rep agent or human-in-the-loop."
        )
        sys.exit(0)

    # Dev stub placeholder
    print("Dev stub: stateful runner not implemented in this deliverable.")

if __name__ == "__main__":
    main()
