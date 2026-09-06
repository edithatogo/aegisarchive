# Static capture acceptance review

Result: passed for the declared static resource graph. Reviewed implementation commits from 5a3c139 through 495c0be20fe5528cac1974b498a766d86af54366.

| Contract | Evidence | Result |
| --- | --- | --- |
| R1 / AC1 | Shared HTML/CSS vectors; loopback CLI and browser-engine nine-resource URL/hash graph, nested imports, cycles, encodings, query identity and readable redirects | Pass |
| R2 / AC2 | Missing resources, path/domain exclusions, robots denial, retry/politeness regressions and browser opaque responses | Pass |
| R3 / AC2 | Coverage resource outcomes, counts, extractor version, archive hashes, empty/pending and script limitations | Pass |
| AC3 | CLI WARC/CDX verifier and complete repository test gate | Pass |
| Code style | Standard-library Python, vanilla UMD JavaScript, existing APIs, focused unittest/node:test cases | Pass |
| Platform guides | No platform guide manifest selected; local Chrome UI exercised | Not applicable beyond recorded local run |

Review fixes (495c0be): srcset candidates separated by commas without descriptors, first duplicate HTML attribute semantics, credential-bearing CLI URL rejection, and browser robots 401/403 denial. Negative loopback coverage tests also cover missing resources and scope/robots exclusions. The failing srcset vector was observed before the fix.

Validation commands and exact counts are retained in validation.json. No runtime dependencies were added. Discovery never executes source scripts. Profiles and leak prevention passed; Python help entry points and compilation passed.

## Browser acceptance

Actual Chrome UI on this Mac used same-origin loopback synthetic fixtures. The readable variant removed the redirect link and captured all eight expected resources, including nested CSS, images and font: coverage complete. A separate fixture including a redirect captured nine of ten discovered URLs (the entry page was also served at a second path); the remaining redirect was opaque and explicitly unsupported, so coverage was incomplete. These UI observations supplement, rather than replace, exact-byte automated assertions. Browser observations used the T6 implementation; subsequent review fixes were verified by the full regression suite and do not change this fixture.

## Claim boundaries

Complete means the discovered, supported static graph has no recorded omissions. This is not a universal browser parser or proof that an arbitrary website has no undiscovered content. The frozen HTML/CSS grammar is the supported acceptance contract; uncommon markup, named entities and newer CSS resource syntax have not received comprehensive conformance qualification. Browser Fetch restrictions can prevent redirect or cross-origin capture. Script-generated content is explicitly flagged. CLI partial runs retain their existing exit-code behavior and expose incompleteness in the coverage receipt. Frontier-only checkpoint import cannot claim a complete archive.

Large response bodies and final browser archive hashing still use memory; no large-site streaming capacity claim is made. Offline navigation, authenticated acquisition, durable archive resume, rendered capture, and Windows/native mirroring acceptance belong to their separate roadmap tracks. No release or live deployment acceptance is claimed here.
