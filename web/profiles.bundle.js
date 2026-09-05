// GENERATED FILE - do not edit. Source: profiles/*.json. Regenerate: python3 scripts/build_profile_bundle.py
;(function (root) {
  var PROFILES = {
  "default_polite": {
    "archival": {
      "deduplicate_payloads": true,
      "enable_opfs_streaming": true,
      "generate_cdx": true,
      "operator": "AegisArchive Preservationist",
      "organization": "Independent Digital Preservation",
      "warc_prefix": "aegis_preservation"
    },
    "description": "Ethical, high-fidelity archival with polite human-cadence delays and dynamic EWMA backoff.",
    "politeness": {
      "adaptive_ewma_backoff": true,
      "burst_limit": 3,
      "concurrency": 1,
      "consecutive_error_tripwire": 3,
      "cooldown_seconds": 60,
      "jitter_distribution": "gaussian",
      "max_delay_ms": 3200,
      "max_requests_per_minute": 25,
      "min_delay_ms": 1200,
      "respect_retry_after": true
    },
    "profile_id": "default_polite",
    "profile_name": "Default Server-Preserving Preservation",
    "target": {
      "allowed_domains": [
        "example.org"
      ],
      "asset_extensions": [
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".csv",
        ".zip",
        ".png",
        ".jpg",
        ".svg"
      ],
      "max_depth": 4,
      "max_pages": 2000,
      "path_blacklist_regex": "/logout|/signin|/signup|/auth|/cgi-bin",
      "path_whitelist_regex": "",
      "seed_urls": {
        "tier_1_core": [
          "https://example.org/"
        ],
        "tier_2_breadth": [],
        "tier_3_discovery": []
      }
    },
    "taxonomy": [
      {
        "code": "DOC",
        "keywords": [
          "documentation",
          "guide",
          "manual",
          "handbook"
        ],
        "label": "Official Documentation"
      },
      {
        "code": "POL",
        "keywords": [
          "policy",
          "standard",
          "governance",
          "charter",
          "procedure"
        ],
        "label": "Policies & Standards"
      },
      {
        "code": "REP",
        "keywords": [
          "report",
          "whitepaper",
          "publication",
          "audit",
          "review"
        ],
        "label": "Reports & Publications"
      }
    ]
  },
  "enterprise_intranet": {
    "archival": {
      "deduplicate_payloads": true,
      "enable_opfs_streaming": true,
      "generate_cdx": true,
      "operator": "Enterprise Records Officer",
      "organization": "Enterprise Records & Compliance",
      "warc_prefix": "enterprise_intranet"
    },
    "description": "Low-impact crawl profile designed for internal enterprise portals (commercial CMS and collaboration platforms).",
    "politeness": {
      "adaptive_ewma_backoff": true,
      "burst_limit": 3,
      "concurrency": 1,
      "consecutive_error_tripwire": 3,
      "cooldown_seconds": 90,
      "jitter_distribution": "gaussian",
      "max_delay_ms": 4000,
      "max_requests_per_minute": 20,
      "min_delay_ms": 1500,
      "respect_retry_after": true
    },
    "profile_id": "enterprise_intranet",
    "profile_name": "Enterprise Intranet & Portal Preservation",
    "target": {
      "allowed_domains": [
        "intranet.local"
      ],
      "asset_extensions": [
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".csv",
        ".zip"
      ],
      "max_depth": 6,
      "max_pages": 5000,
      "path_blacklist_regex": "/calendar/|/staff-directory|/events/|/search/",
      "path_whitelist_regex": "",
      "seed_urls": {
        "tier_1_core": [
          "https://intranet.local/portal"
        ],
        "tier_2_breadth": [
          "https://intranet.local/documents",
          "https://intranet.local/policies"
        ],
        "tier_3_discovery": [
          "https://intranet.local/"
        ]
      }
    },
    "taxonomy": [
      {
        "code": "GOV",
        "keywords": [
          "governance",
          "board",
          "committee",
          "charter",
          "delegation"
        ],
        "label": "Corporate Governance"
      },
      {
        "code": "OPS",
        "keywords": [
          "procedure",
          "sop",
          "protocol",
          "guideline",
          "workflow"
        ],
        "label": "Operational Protocols"
      },
      {
        "code": "AUD",
        "keywords": [
          "audit",
          "risk",
          "compliance",
          "incident",
          "quality"
        ],
        "label": "Risk & Quality Audits"
      }
    ]
  },
  "rapid_research": {
    "archival": {
      "deduplicate_payloads": true,
      "enable_opfs_streaming": true,
      "generate_cdx": true,
      "operator": "Research Analyst",
      "organization": "Academic / Research Lab",
      "warc_prefix": "rapid_research"
    },
    "description": "Fast harvesting profile for authorized research servers, local staging environments, or test mirrors.",
    "politeness": {
      "adaptive_ewma_backoff": true,
      "burst_limit": 10,
      "concurrency": 1,
      "consecutive_error_tripwire": 5,
      "cooldown_seconds": 30,
      "jitter_distribution": "uniform",
      "max_delay_ms": 600,
      "max_requests_per_minute": 180,
      "min_delay_ms": 250,
      "respect_retry_after": true
    },
    "profile_id": "rapid_research",
    "profile_name": "Authorized High-Throughput Research",
    "target": {
      "allowed_domains": [
        "localhost",
        "127.0.0.1"
      ],
      "asset_extensions": [
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".csv",
        ".zip",
        ".png",
        ".jpg"
      ],
      "max_depth": 8,
      "max_pages": 10000,
      "path_blacklist_regex": "",
      "path_whitelist_regex": "",
      "seed_urls": {
        "tier_1_core": [
          "http://127.0.0.1:8000/"
        ],
        "tier_2_breadth": [],
        "tier_3_discovery": []
      }
    },
    "taxonomy": [
      {
        "code": "RES",
        "keywords": [
          "dataset",
          "paper",
          "study",
          "methodology",
          "results"
        ],
        "label": "Research Output"
      }
    ]
  }
};
  root.AEGIS_BUNDLED_PROFILES = PROFILES;
  if (typeof module === 'object' && module.exports) { module.exports = PROFILES; }
})(typeof self !== 'undefined' ? self : globalThis);
