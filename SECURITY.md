# Security

## Reporting a vulnerability

Please report security issues privately by emailing **2086695957@qq.com** with the subject line `SECURITY:`. Do **not** open a public issue for a vulnerability — issues on this repository are public.

We aim to acknowledge reports within 2 business days and provide a fix or mitigation timeline within 14 days for high-severity issues.

---

## Verifying your download

**This project does not ship build-provenance attestations.** Wheels are built and uploaded by hand from a local build. There is no CI signing identity behind them, no Sigstore signature, and no Rekor transparency-log entry. Commands such as `gh attestation verify` and `cosign verify-blob` will **not** succeed for this package — if anything claims otherwise, treat that as a red flag.

What you can actually verify today:

**1. PyPI's own digests.** PyPI records a SHA-256 for every uploaded file. Compare it against the file you downloaded, either on the version page under "Download files", or:

```sh
curl -s https://pypi.org/pypi/ai-aegis/1.0.0/json \
  | python -c "import json,sys; [print(f['filename'], f['digests']['sha256']) for f in json.load(sys.stdin)['urls']]"
```

**2. Build it from source.** The source distribution (`ai_aegis-1.0.0.tar.gz`) carries the full source. Building it yourself removes the need to trust the uploaded wheel at all:

```sh
pip download --no-binary :all: ai-aegis
python -m build
```

Neither check proves the code is *safe* — only that you received the bytes we published. A wheel that installs cleanly and matches its digest can still do something harmful. There is no substitute for reading the code you run, and that goes double for a security tool that sits between your agent and the outside world.
