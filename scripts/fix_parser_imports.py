fixes = {
    "ofx.py": "import re\n",
    "xml_parser.py": "import re\nimport xml.etree.ElementTree as ET\n",
    "pdf.py": (
        "import io\nimport logging\nimport re\nfrom typing import Optional\n\n"
        "import pdfplumber\nfrom fastapi import HTTPException\n\n"
        "log = logging.getLogger('orgconc.parsers')\n\n"
    ),
    "router.py": (
        "from pathlib import Path\n\nfrom fastapi import HTTPException\n\n"
        "from api.parsers.ofx import _parse_ofx\n"
        "from api.parsers.pdf import _parse_pdf\n"
        "from api.parsers.xml_parser import _parse_xml\n\n"
    ),
    "classifier.py": "",
    "anomalies.py": (
        "from collections import Counter\nfrom itertools import combinations\n\n"
    ),
    "stats.py": (
        "import re\nfrom collections import defaultdict\n\n"
        "from api.parsers.classifier import _classificar\n\n"
    ),
}
from pathlib import Path
for fname, imp in fixes.items():
    p = Path("api/parsers") / fname
    body = p.read_text(encoding="utf-8")
    if "from __future__" in body:
        body = body.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\n" + imp,
            1,
        )
    p.write_text(body, encoding="utf-8")
print("fixed")
