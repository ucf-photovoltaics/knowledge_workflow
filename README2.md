
Knowledge Workflow
Extract structured data from scientific papers in your Zotero library using Claude AI. Point it at a collection, get back CSV files with paper metadata and domain-specific concepts extracted from full-text PDFs.

What This Does
Takes a Zotero collection of research papers and extracts structured information into CSV format. Two extraction approaches:

V3: Define your schema upfront (or use defaults), get one row per paper with fixed columns
V4: Two-stage extraction that discovers concepts from abstracts, then mines full text for values
Both read PDFs from Zotero, both output CSV. V3 is faster and more predictable. V4 is better when you don't know what questions to ask yet.

Quick Start
Prerequisites
Python 3.13+
uv package manager
Zotero library with PDFs attached to items
Anthropic API key
Installation
# Clone and enter the repo
cd knowledge_workflow

# Install dependencies (creates .venv automatically)
uv sync
Configuration
Create a .env file in the project root:

ANTHROPIC_API_KEY=sk-ant-api03-...
ZOTERO_API_KEY=your_zotero_api_key
Update the Zotero connection settings at the top of the script you're running:

LIBRARY_ID   = '2189702'        # Your Zotero library ID
LIBRARY_TYPE = 'group'          # 'user' or 'group'
API_KEY      = ''               # Now reads from .env via ZOTERO_API_KEY
Run V3 (Structured Extraction)
# Edit scripts/knowledge_workflow_V3.py
# Set collection_name = 'Your Collection Name'

uv run python scripts/knowledge_workflow_V3.py
Output: extraction_<collection>-<user>-v3-<date>.csv

Run V4 (Two-Stage Discovery)
# Edit scripts/knowledge_workflow_V4.py  
# Set collection_name = 'Your Collection Name'

uv run python scripts/knowledge_workflow_V4.py
Outputs:

concepts_<collection>-<user>-v4-<date>.csv (flat extraction table)
schema_<collection>-<user>-v4-<date>.csv (wide-format schema with source quotes)
Copy saved to schemas/<collection>/ for reuse
Usage Examples
Extract Device Parameters from Solar Cell Papers (V3)
# scripts/knowledge_workflow_V3.py

# Use default concepts (absorber composition, bandgap, etc.)
CONCEPTS_CSV_PATH = ''

# Or load from a previous V4 run
CONCEPTS_CSV_PATH = 'schemas/cdte/schema_cdte-Brent_Thompson-v4-20260311.csv'
CONCEPTS_COLUMN   = 'concept'

collection_name = 'CdTe-CdSeTe_PV'
Result: One row per paper, columns for Title, Author, Institution, Country, DOI, Device Type, plus your concept columns (e.g., "absorber composition", "absorber bandgap eV", "device efficiency").

Discover What's Novel in a New Literature Set (V4)
# scripts/knowledge_workflow_V4.py

# Let Claude extract concepts from abstracts
USE_CSV_CONCEPTS = False

collection_name = 'TEM-Semiconductors'
TOP_N_PER_PAPER  = 25  # Extract top 25 concepts per paper
V4 will:

Extract 25 concepts from each paper's abstract
Normalize them (merge "open circuit voltage" and "Voc" → "open circuit voltage")
Mine full PDF text for paper-specific values and source sentences
Output wide schema with concept columns and "value | quote" cells
Reuse a Known Schema Across Collections (V4)
# scripts/knowledge_workflow_V4.py

# Skip concept extraction, use existing schema
USE_CSV_CONCEPTS  = True
CONCEPTS_CSV_PATH = 'schemas/cdte/schema_cdte-Brent_Thompson-v4-20260311.csv'
CONCEPTS_COLUMN   = 'absorber composition'  # or any column name from that CSV

collection_name = 'Perovskites'
This populates the same concept columns across different paper collections for easier comparison.

When to Use V3 vs V4
Use V3 when:

You know exactly what data points you need
You want consistent output structure across runs
Speed matters (V3 is ~2x faster)
You're working with a well-defined domain
Use V4 when:

Exploring a new domain or literature set
You want to discover what's actually reported in papers
You need source sentences for provenance/validation
Building a reusable schema for future collections
Combine them: Run V4 once on a representative collection to build your schema, then use that schema in V3 for faster extraction on new papers.

Output Files
V3 Output
extraction_<collection>-<user>-v3-<date>.csv:

Title	Author	Institution	Country	DOI	Device Type	absorber composition	absorber bandgap eV	...
CdTe solar cells with...	Smith	MIT	USA	https://doi.org/...	photovoltaic cell	CdSexTe1-x	1.45	...
V4 Outputs
concepts_<collection>-<user>-v4-<date>.csv (flat):

paper	doi	canonical	paper_term	relevance
CdTe solar cells...	10.xxx	absorber composition	CdSexTe1-x	0.92
CdTe solar cells...	10.xxx	device efficiency	22.1%	0.88
schema_<collection>-<user>-v4-<date>.csv (wide):

domain	doi	absorber composition	device efficiency	...
cdte	10.xxx	CdSexTe1-x | "The absorber layer consisted of CdSexTe1-x with x=0.3"	22.1% | "Champion device achieved 22.1% power conversion efficiency"	...
The schema CSV is also copied to schemas/<collection>/ for reuse in later runs.

Project Structure
knowledge_workflow/
├── scripts/
│   ├── knowledge_workflow_V3.py    # Claude-based structured extraction
│   ├── knowledge_workflow_V4.py    # Two-stage concept discovery
│   ├── knowledge_workflow_V1.py    # Legacy: spaCy + TF-IDF
│   ├── knowledge_workflow_V2.py    # Legacy: KeyBERT
│   └── zotero_bulk_read.py        # Legacy: spaCy extraction
├── schemas/                        # Reference concept lists & schemas
│   ├── cdte/
│   ├── tem-semiconductors/
│   └── knowledge_management/
├── outputs/                        # Generated CSV files
├── docs/
│   ├── V3_GUIDE.md                # V3 detailed documentation
│   ├── V4_GUIDE.md                # V4 detailed documentation
│   └── ARCHITECTURE.md            # System design & pipeline comparison
├── .env                           # API keys (not committed)
├── pyproject.toml                 # Dependencies
└── README.md                      # This file
Configuration Reference
Both V3 and V4 share these settings (at top of each script):

LIBRARY_ID        = '2189702'           # Zotero library ID
LIBRARY_TYPE      = 'group'             # 'user' or 'group'  
API_KEY           = ''                  # Reads from .env (ZOTERO_API_KEY)
MODEL             = 'claude-sonnet-4-6' # Anthropic model
RATE_LIMIT_DELAY  = 0.5                 # Seconds between API calls
V3-specific:

CONCEPTS_CSV_PATH = ''                  # Path to schema CSV (optional)
CONCEPTS_COLUMN   = 'concept'           # Column to read from that CSV
V4-specific:

USE_CSV_CONCEPTS     = False            # Skip Phase 1 if True
CONCEPTS_CSV_PATH    = ''               # Path to existing schema
CONCEPTS_COLUMN      = 'concept'        # Column name in that CSV
TOP_N_PER_PAPER      = 25               # Concepts extracted per paper (Phase 1)
FULL_TEXT_MAX_CHARS  = 80_000           # Chars sent to Claude (Phase 2)
API Costs
Rough estimates (as of March 2025, Claude Sonnet 4 pricing):

V3: ~$0.01-0.03 per paper (depends on concept count)
V4 Phase 1: ~$0.01 per paper (abstract extraction)
V4 Phase 2: ~$0.05-0.15 per paper (full-text mining)
For a 50-paper collection:

V3: ~$1-2
V4: ~$3-8
Rate limiting (RATE_LIMIT_DELAY = 0.5) keeps you under API tier limits. Adjust as needed.

Troubleshooting
"ModuleNotFoundError: No module named 'anthropic'"

uv sync
Papers showing "Not Specified" for everything

Check that PDFs are attached in Zotero. The script needs full text, not just metadata. Papers without PDFs will fall back to abstract-only extraction (V4) or return "Not Specified" (V3).

Claude rate limit errors

Increase RATE_LIMIT_DELAY to 1.0 or higher.

V3 missing concepts I know are in the papers

Try V4 first to see what concepts are actually discoverable. V3 only extracts what you explicitly tell it to look for. If concepts aren't in your schema, they won't appear.

V4 schema has too many columns

Lower TOP_N_PER_PAPER or edit the normalized concept list manually. The normalization step tries to reduce redundancy but might still produce 50-80 columns for diverse collections.

Further Reading
V3_GUIDE.md — How V3 works, configuration, output format
V4_GUIDE.md — V4 two-stage process, when to use, configuration
ARCHITECTURE.md — System design, pipeline comparison, Zotero integration
License
MIT
