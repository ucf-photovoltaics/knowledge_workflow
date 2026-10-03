from typing import Any, Dict, List, Optional
import requests
from fastmcp import FastMCP
import xml.etree.ElementTree as ET


MDS_PREFIX = "https://cwrusdle.bitbucket.io/mds/"
SKOS_PREFIX = "http://www.w3.org/2004/02/skos/core#"
RDFS_PREFIX = "http://www.w3.org/2000/01/rdf-schema#"
CCO_PREFIX = "https://www.commoncoreontologies.org/"

# Expanded Property URIs mapped from your ontology file
PROPERTY_MAP = {
    # Core MDS Properties
    "domain": f"{MDS_PREFIX}hasDomain",
    "subDomain": f"{MDS_PREFIX}hasSubDomain",
    "studyStage": f"{MDS_PREFIX}hasStudyStage",
    "unit": f"{MDS_PREFIX}unit",
   
    # Standard SKOS/RDFS Properties found in file
    "definition": f"{SKOS_PREFIX}definition",
    "altLabel": f"{SKOS_PREFIX}altLabel",
    "example": f"{SKOS_PREFIX}example",
    "scopeNote": f"{SKOS_PREFIX}scopeNote",
    "comment": f"{RDFS_PREFIX}comment",
    "seeAlso": f"{RDFS_PREFIX}seeAlso",
   
    # Common Core Ontology references found in file (often used for Source URLs like Wikipedia)
    "sourceUrl": f"{CCO_PREFIX}ont00001754"
}

def search_mdsonto(
    query: str,
    api_key: Optional[str] = None,
    ontologies: Optional[List[str]] = None,
    require_exact_match: bool = False,
    also_search_properties: bool = True, # Default to True to search within definitions/domains
    also_search_obsolete: bool = False,
    max_page_size: int = 50,
    max_records: Optional[int] = None,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Search for ontology terms in BioPortal/OntoPortal using the search endpoint.
    Modified to include property data in the retrieval.
    """
    # Callers must provide their configured API key; no embedded fallback.
   
    if api_key is None:
        raise ValueError("API key is required.")
   
    base_url = "https://www.mdsonto-portal.com:8443"
    endpoint_url = f"{base_url}/search"
   
    all_records = []
    page = 1
   
    # Include specific fields to ensure we get the definition and MDS properties
    include_fields = ["prefLabel", "synonym", "definition", "properties", "cui", "semanticType"]
   
    while True:
        params = {
            "q": query,
            "apikey": api_key,
            "page": page,
            "pagesize": max_page_size,
            "require_exact_match": "true" if require_exact_match else "false",
            "also_search_properties": "true" if also_search_properties else "false",
            "also_search_obsolete": "true" if also_search_obsolete else "false",
            "include": ",".join(include_fields)  # Request properties specifically
        }
       
        if ontologies:
            params["ontologies"] = ",".join(ontologies)
       
        try:
            response = requests.get(endpoint_url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"Error fetching from Portal: {e}")
            break
        except ValueError as e:
            if verbose:
                print(f"Error parsing JSON response: {e}")
            break
       
        if isinstance(data, dict) and 'collection' in data:
            records = data['collection']
        elif isinstance(data, list):
            records = data
        else:
            if verbose:
                print(f"Unexpected response format: {type(data)}")
            break
       
        if not records:
            break
       
        all_records.extend(records)
       
        if verbose:
            print(f"Fetched {len(records)} records from page {page}")
       
        if max_records is not None and len(all_records) >= max_records:
            all_records = all_records[:max_records]
            break
       
        if len(records) < max_page_size:
            break
       
        page += 1
   
    return all_records

def _extract_property(properties: Dict, uri: str) -> str:
    """Helper to safely extract a property value from the properties dict."""
    if not properties:
        return "N/A"
   
    val = properties.get(uri)
    if not val:
        return "N/A"
   
    # OntoPortal often returns properties as lists, even for single values
    if isinstance(val, list):
        return "; ".join([str(v) for v in val if v])
    return str(val)

# MCP TOOL SECTION
def search_mds_ontology(
    query: str,
    ontologies: Optional[str] = None,
    max_results: int = 1000,
    require_exact_match: bool = False,
    search_in_properties: bool = True,
    api_key: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Search for terms in the MDS Ontology (or others) and retrieve MDS-specific metadata.
   
    This function searches for terms and extracts specific MDS annotation properties defined
    in MDS_Onto.ttl, specifically:
      - skos:definition
      - mds:hasDomain
      - mds:hasSubDomain
      - mds:hasStudyStage
   
    Args:
        query: The search term (e.g., "syringe", "temperature", "silicon").
        ontologies: Comma-separated list of ontology acronyms (e.g., "MDS-ONTO").
        max_results: Maximum number of results to return (default: 10).
        require_exact_match: If True, only return exact matches.
        search_in_properties: If True, the query will also match text found inside definitions
                              and domains, not just the label.
        api_key: BioPortal API key.
   
    Returns:
        List[Dict[str, str]]: A list of dictionaries containing term details including
                              MDS specific properties.
    """
    try:
        ontology_list = None
        if ontologies:
            ontology_list = [ont.strip() for ont in ontologies.split(",")]
       
        results = search_mdsonto(
            query=query,
            api_key=api_key,
            ontologies=ontology_list,
            require_exact_match=require_exact_match,
            also_search_properties=search_in_properties,
            max_records=max_results,
            verbose=False
        )
       
        processed_results = []
        for result in results:
            term_id = result.get('@id', '')
            pref_label = result.get('prefLabel', '')
           
            # Extract Ontology Acronym
            ontology_acronym = 'Unknown'
            if 'links' in result and 'ontology' in result['links']:
                ontology_url = result['links']['ontology']
                if ontology_url:
                    ontology_acronym = ontology_url.split('/')[-1]
           
            # Extract Properties
            # Note: The search API puts custom properties inside a 'properties' dict key
            # provided we requested include='properties'
            props = result.get('properties', {})
           
            definition = _extract_property(props, PROPERTY_MAP["definition"])
            domain = _extract_property(props, PROPERTY_MAP["domain"])
            sub_domain = _extract_property(props, PROPERTY_MAP["subDomain"])
            study_stage = _extract_property(props, PROPERTY_MAP["studyStage"])
           
            # If definition wasn't in properties, check the top-level 'definition' field
            if definition == "N/A" and result.get('definition'):
                # API sometimes returns definition as a list of strings at the root
                defs = result.get('definition')
                if isinstance(defs, list):
                    definition = "; ".join(defs)
                else:
                    definition = str(defs)
           
            if term_id and pref_label:
                processed_results.append({
                    "Label": pref_label,
                    "ID": term_id,
                    "Ontology": ontology_acronym,
                    "Definition": definition,
                    "MDS_Domain": domain,
                    "MDS_SubDomain": sub_domain,
                    "MDS_StudyStage": study_stage
                })
       
        return processed_results
   
    except Exception as e:
        print(f"Error executing search: {e}")
        return []


def get_ontology_domains() -> List[str]:
    """
    Downloads the MDS Ontology OWL file directly and extracts all unique
    'mds:hasDomain' values.
   
    This bypasses the search API to ensure all defined domains are found
    directly from the source file.
    """
   
    # The direct file location you provided
    owl_url = "https://cwrusdle.bitbucket.io/files/MDS_Onto-v0.3.1.14.owl"
   
    try:
        # 1. Download the file
        print(f"Fetching ontology from: {owl_url}")
        response = requests.get(owl_url)
        response.raise_for_status()
       
        # 2. Parse the XML content
        # .owl files are typically RDF/XML
        root = ET.fromstring(response.content)
        unique_domains = set()
        unique_subdomains = set()
       
        # 3. Iterate through all tags to find 'hasDomain'
        # We use strict string checking for the tag name to handle namespaces gracefully.
        # The tag will likely look like: {https://cwrusdle.bitbucket.io/mds/}hasDomain
        for elem in root.iter():
            if not elem.text: continue
            clean_text = elem.text.strip()
            if not clean_text: continue

            # "endswith" handles the namespace prefix automatically
            if elem.tag.endswith("hasDomain"):
                unique_domains.add(clean_text)
            elif elem.tag.endswith("hasSubDomain"):
                unique_subdomains.add(clean_text)
           
        print(unique_domains)
        print(unique_subdomains)    
        return {
            "domains": sorted(list(unique_domains)),
            "subdomains": sorted(list(unique_subdomains))
        }
    except Exception as e:
        return {"error": str(e), "domains": [], "subdomains": []}

mcp = FastMCP("mds-onto_mcp")
mcp.tool(search_mds_ontology)
mcp.tool(get_ontology_domains)

def main():
    """
    Main entry point.
    1. If run normally, starts the MCP Server.
    2. If you want to SEE the domains immediately, uncomment the lines below.
    """
   
    # --- DEBUG: Uncomment to print domains without starting server ---
    # print("Fetching domains...")
    # data = get_ontology_domains()
    # print(f"\nFOUND {len(data['domains'])} DOMAINS:")
    # for d in data['domains']: print(f" - {d}")
    # print(f"\nFOUND {len(data['subdomains'])} SUB-DOMAINS:")
    # for s in data['subdomains']: print(f" - {s}")
    # return
    # ---------------------------------------------------------------

    mcp.run()

if __name__ == "__main__":
    main()
