"""Write way/duties.json in its readable layout: one duty (and one attestation) per line."""
import json, sys


def dump(d, path):
    out = ["{"]
    keys = list(d)
    for i, k in enumerate(keys):
        end = "," if i < len(keys) - 1 else ""
        v = d[k]
        if k in ("duties", "attest") and isinstance(v, list):
            body = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in v)
            out.append(' %s: [\n%s\n ]%s' % (json.dumps(k), body, end) if v else ' %s: []%s' % (json.dumps(k), end))
        else:
            out.append(" %s: %s%s" % (json.dumps(k), json.dumps(v, ensure_ascii=False, indent=2).replace("\n", "\n "), end))
    out.append("}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "way/duties.json"
    dump(json.load(open(p, encoding="utf-8")), p)
