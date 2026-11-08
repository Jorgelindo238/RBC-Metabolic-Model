"""Archive pinned RBC-GEM sources; never execute downloaded repository code."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
COMMITS = {"1.2.0": "5347d80275be01e410aa9787b0aac99497a8ed57",
           "1.3.0": "43fd381d9eb8a8a4079629012362312960e1c009"}
PATHS = (
    "README.md", "HISTORY.md", "version.txt", "model/RBC-GEM.json",
    "model/genes.tsv", "model/metabolites.tsv", "model/reactions.tsv",
    "data/curation/reactions_evidence.tsv", "data/curation/genes_evidence.tsv",
    "data/curation/genes_removals.tsv", "data/curation/reactions_removals.tsv",
    "data/curation/reactions_updated_1.3.0.tsv", "data/curation/complexes.tsv",
    "data/annotation/reactions_References.tsv", "data/annotation/genes_References.tsv",
    "data/external/proteomics/proteomic_evidence_table.tsv",
    "data/external/database/additional_references_manual.tsv",
    "data/external/database/references_RBC-GEM.tsv",
)


def fetch(url, limit=90_000_000):
    request = urllib.request.Request(url, headers={"User-Agent": "AIRBC-source-audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise ValueError("download exceeds declared size limit")
        return payload, response.headers.get_content_type()


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "output/rbc_gem_network_audit_2026_10_06")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    snapshots = out / "original_local_sources"
    snapshots.mkdir()
    inputs = {}
    for name in ("RBC/Rxn_RBC.txt", "src/equadiff_brodbar.py", "src/rbc_stoichiometry.py",
                 "src/reaction_positivity.py", "src/Data_Bordbar_et_al_exp.xlsx",
                 "config/fla_working_reference.json"):
        payload = (ROOT / name).read_bytes()
        (snapshots / Path(name).name).write_bytes(payload)
        inputs[name] = sha(payload)
    (out / "original_local_hashes.json").write_text(json.dumps(inputs, indent=2) + "\n")
    receipts = []

    def save(url, name, *, md5=None, git_blob=None):
        try:
            payload, kind = fetch(url)
            if md5 and hashlib.md5(payload).hexdigest() != md5:
                raise ValueError("Figshare MD5 mismatch")
            if git_blob:
                actual = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
                if actual != git_blob:
                    raise ValueError("Git blob hash mismatch")
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".json"):
                json.loads(payload)
            elif name.endswith(".xlsx"):
                with zipfile.ZipFile(__import__("io").BytesIO(payload)) as archive:
                    if archive.testzip() is not None:
                        raise ValueError("Excel ZIP CRC failed")
            target.write_bytes(payload)
            receipts.append({"url": url, "file": name, "bytes": len(payload), "content_type": kind,
                             "sha256": sha(payload), "provider_md5_verified": bool(md5),
                             "git_blob_verified": bool(git_blob), "status": "retrieved"})
            print(f"retrieved {name}: {len(payload)} bytes", flush=True)
            return payload
        except Exception as exc:
            receipts.append({"url": url, "file": name, "status": "unavailable", "error": str(exc)})
            print(f"unavailable {name}: {exc}", flush=True)
            return None
        finally:
            (out / "retrieval_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")

    for version, commit in COMMITS.items():
        raw = save(f"https://api.github.com/repos/z-haiman/RBC-GEM/git/trees/{commit}?recursive=1",
                   f"github/{version}/tree.json")
        if raw is None:
            raise RuntimeError("cannot verify pinned Git tree")
        tree = {entry["path"]: entry for entry in json.loads(raw)["tree"]}
        names = PATHS if version == "1.3.0" else ("model/RBC-GEM.json", "version.txt")
        for name in names:
            if name not in tree:
                continue
            save(f"https://raw.githubusercontent.com/z-haiman/RBC-GEM/{commit}/{name}",
                 f"github/{version}/{name}", git_blob=tree[name]["sha"])

    raw = save("https://api.figshare.com/v2/articles?resource_doi=10.1371/journal.pcbi.1012109&page_size=100",
               "supplements/article_index.json")
    if raw:
        for article in json.loads(raw):
            title = article["title"]
            if not any(word in title.lower() for word in ("reconstruction", "connectivity", "systems biology markup")):
                continue
            metadata = save(f"https://api.figshare.com/v2/articles/{article['id']}",
                            f"supplements/article_{article['id']}.json")
            if metadata:
                for file in json.loads(metadata)["files"]:
                    save(file["download_url"], "supplements/" + file["name"], md5=file["computed_md5"])
    if not (out / "github/1.3.0/model/RBC-GEM.json").exists():
        raise RuntimeError("required RBC-GEM JSON unavailable")
    print(json.dumps({"commits": COMMITS, "retrieved": sum(r["status"] == "retrieved" for r in receipts),
                      "unavailable": sum(r["status"] != "retrieved" for r in receipts),
                      "out": str(out)}))


if __name__ == "__main__":
    main()
