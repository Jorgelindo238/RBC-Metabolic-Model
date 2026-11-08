"""One-shot entry point bridging the immutable fit and full-audit adapters."""

import argparse
import json
from pathlib import Path

from restore_broad_interior import restore
from finish_broad_restoration import finish


def execute(parent, out):
    try:
        return restore(parent, out)
    except FileNotFoundError as error:
        expected = out/"fits/control/trace.jsonl"
        if (not error.filename or Path(error.filename).resolve() != expected.resolve()
                or not (out/"fits/restoration/files_seal.json").exists()):
            raise
        return finish(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.parent.resolve(), args.out.resolve()), indent=2))
