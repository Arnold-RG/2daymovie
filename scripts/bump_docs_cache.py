from pathlib import Path

root = Path(__file__).resolve().parents[1] / "docs"
updated = 0
for path in root.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    next_text = (
        text.replace("style.css?v=20261013", "style.css?v=20261015d")
        .replace("script.js?v=20261013", "script.js?v=20261015d")
        .replace('content="#070605"', 'content="#0A0A0A"')
    )
    if next_text != text:
        path.write_text(next_text, encoding="utf-8")
        updated += 1
print(f"updated {updated} html files")
