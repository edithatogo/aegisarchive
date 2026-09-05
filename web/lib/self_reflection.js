/**
 * AegisArchive - Self-Reflection & Forensic Diagnostic Engine
 * 
 * Provides automated post-crawl quality assessment:
 * - Route yield & directory density analysis
 * - Server strain & latency percentile evaluation (p50, p90, p99)
 * - Error tripwire and broken link auditing
 * - Dynamic taxonomy classification and gap identification based on profile
 * 
 * Licensed under the Apache License, Version 2.0.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SelfReflectionEngine = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  const KNOWN_LOW_YIELD_PATTERNS = [
    { pattern: /\/calendar\b/i, reason: "Calendar, schedule, and date-loop traps" },
    { pattern: /\/events\b/i, reason: "Ephemeral event notices without archival policy content" },
    { pattern: /\/login\b|\/auth\b/i, reason: "Authentication gateways" },
    { pattern: /\/search\b/i, reason: "Dynamic search query pages" },
    { pattern: /\/tag\b|\/tags\b/i, reason: "Tag taxonomies with duplicate link loops" }
  ];

  function analyze(telemetry, profile = {}) {
    const {
      auditLedger = [],
      documents = [],
      visited = [],
      queue = [],
      startTime = Date.now(),
      endTime = Date.now()
    } = telemetry;

    const totalPagesCrawled = auditLedger.length;
    const totalDocsRetrieved = documents.length;
    const durationMinutes = Math.max(0.1, (endTime - startTime) / 60000);
    const crawlRate = (totalPagesCrawled / durationMinutes).toFixed(1);

    // 1. Route Yield Analysis
    const routeStats = {};
    for (const item of auditLedger) {
      try {
        const u = new URL(item.url);
        const pathSegments = u.pathname.split('/').filter(Boolean);
        const topSection = pathSegments.length > 0 ? '/' + pathSegments.slice(0, 2).join('/') : '/root';
        
        if (!routeStats[topSection]) {
          routeStats[topSection] = { section: topSection, pages: 0, docs: 0, latencies: [] };
        }
        routeStats[topSection].pages++;
        if (item.latency_ms) routeStats[topSection].latencies.push(item.latency_ms);
      } catch (e) {}
    }

    for (const doc of documents) {
      try {
        const u = new URL(doc.url || 'http://localhost');
        const pathSegments = u.pathname.split('/').filter(Boolean);
        const topSection = pathSegments.length > 0 ? '/' + pathSegments.slice(0, 2).join('/') : '/root';
        if (routeStats[topSection]) {
          routeStats[topSection].docs++;
        }
      } catch (e) {}
    }

    const routeYields = Object.values(routeStats).map(r => {
      const yieldPct = r.pages > 0 ? ((r.docs / r.pages) * 100).toFixed(1) : '0.0';
      const avgLat = r.latencies.length > 0 
        ? Math.round(r.latencies.reduce((a, b) => a + b, 0) / r.latencies.length) 
        : 0;
      return {
        section: r.section,
        pagesCrawled: r.pages,
        documentsRetrieved: r.docs,
        yieldPercentage: parseFloat(yieldPct),
        avgLatencyMs: avgLat
      };
    }).sort((a, b) => b.yieldPercentage - a.yieldPercentage);

    // 2. Latency & Server Health Assessment
    const latencies = auditLedger.map(a => a.latency_ms || 0).filter(l => l > 0).sort((a, b) => a - b);
    const avgLatency = latencies.length > 0 ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : 0;
    const p50Latency = latencies.length > 0 ? latencies[Math.floor(latencies.length * 0.5)] : 0;
    const p90Latency = latencies.length > 0 ? latencies[Math.floor(latencies.length * 0.9)] : 0;
    const p99Latency = latencies.length > 0 ? latencies[Math.floor(latencies.length * 0.99)] : 0;
    const maxLatency = latencies.length > 0 ? Math.max(...latencies) : 0;

    const serverErrors = auditLedger.filter(a => a.status === 429 || a.status >= 500).length;
    const clientErrors = auditLedger.filter(a => a.status >= 400 && a.status < 500 && a.status !== 429).length;

    let serverHealthVerdict = "Optimal";
    const serverRecommendations = [];
    if (serverErrors > 0) {
      serverHealthVerdict = "Degraded (Server Errors Detected)";
      serverRecommendations.push(`Target server returned ${serverErrors} error responses (HTTP 429 / 5xx). Increase polite delay or reduce concurrency.`);
    }
    if (avgLatency > 2000) {
      serverHealthVerdict = "Strained (High Latency)";
      serverRecommendations.push(`Average response latency was high (${avgLatency} ms). The target server may be constrained.`);
    }
    if (serverRecommendations.length === 0) {
      serverRecommendations.push("Server response latencies remained stable throughout the acquisition. Polite flow control was respected.");
    }

    // 3. Low-Yield Route Identification
    const lowYieldSuggestions = [];
    for (const r of routeYields) {
      if (r.pagesCrawled >= 5 && r.documentsRetrieved === 0) {
        let patternMatch = null;
        for (const p of KNOWN_LOW_YIELD_PATTERNS) {
          if (p.pattern.test(r.section)) {
            patternMatch = p.reason;
            break;
          }
        }
        lowYieldSuggestions.push({
          section: r.section,
          pagesCrawled: r.pagesCrawled,
          reason: patternMatch || "Zero documents found across traversed branch. Consider pruning scope to preserve server resources."
        });
      }
    }

    // 4. Dynamic Taxonomy Coverage & Gap Analysis
    const taxonomyDefinitions = profile.taxonomy || [];
    const taxonomyDistribution = {};
    for (const tax of taxonomyDefinitions) {
      taxonomyDistribution[tax.code] = {
        code: tax.code,
        label: tax.label,
        count: 0,
        sampleDocs: []
      };
    }

    for (const doc of documents) {
      const textToSearch = `${doc.title || ''} ${doc.url || ''} ${doc.local_path || ''}`.toLowerCase();
      for (const tax of taxonomyDefinitions) {
        const matches = (tax.keywords || []).some(kw => textToSearch.includes(kw.toLowerCase()));
        if (matches) {
          taxonomyDistribution[tax.code].count++;
          if (taxonomyDistribution[tax.code].sampleDocs.length < 3) {
            taxonomyDistribution[tax.code].sampleDocs.push(doc.title || doc.url);
          }
        }
      }
    }

    const taxonomyGaps = [];
    for (const tax of taxonomyDefinitions) {
      const stats = taxonomyDistribution[tax.code];
      if (stats.count === 0) {
        taxonomyGaps.push({
          code: tax.code,
          label: tax.label,
          message: `Zero documents retrieved matching criteria for '${tax.label}'. Consider targeted search queries or dedicated seed URLs.`
        });
      }
    }

    return {
      summary: {
        totalPagesCrawled,
        totalDocsRetrieved,
        durationMinutes: parseFloat(durationMinutes.toFixed(2)),
        crawlRateReqPerMin: parseFloat(crawlRate),
        avgLatencyMs: avgLatency,
        p50LatencyMs: p50Latency,
        p90LatencyMs: p90Latency,
        p99LatencyMs: p99Latency,
        maxLatencyMs: maxLatency,
        serverErrors,
        clientErrors,
        serverHealthVerdict
      },
      routeYields,
      serverRecommendations,
      lowYieldSuggestions,
      taxonomyDistribution: Object.values(taxonomyDistribution),
      taxonomyGaps
    };
  }

  function generateMarkdownReport(analysis, profile = {}) {
    const s = analysis.summary;
    const profileName = profile.profile_name || 'Generic Web Archiving';
    let md = `# AegisArchive: Self-Reflection & Diagnostic Report\n\n`;
    md += `**Profile**: ${profileName}  \n`;
    md += `**Generated**: ${new Date().toISOString()}  \n`;
    md += `**Server Health Status**: **${s.serverHealthVerdict}**\n\n`;

    md += `## 1. Executive Telemetry\n\n`;
    md += `| Metric | Value |\n| :--- | :--- |\n`;
    md += `| Total Pages Crawled | **${s.totalPagesCrawled}** |\n`;
    md += `| Assets Retrieved | **${s.totalDocsRetrieved}** |\n`;
    md += `| Total Run Duration | ${s.durationMinutes} min |\n`;
    md += `| Effective Crawl Rate | ${s.crawlRateReqPerMin} req/min |\n`;
    md += `| Avg Latency (p50 / p90 / p99) | ${s.avgLatencyMs} ms (${s.p50LatencyMs} / ${s.p90LatencyMs} / ${s.p99LatencyMs} ms) |\n`;
    md += `| Server Errors (HTTP 429/5xx) | ${s.serverErrors} |\n`;
    md += `| Client Errors (HTTP 4xx) | ${s.clientErrors} |\n\n`;

    md += `## 2. Server Strain & Politeness Findings\n\n`;
    for (const rec of analysis.serverRecommendations) {
      md += `* ${rec}\n`;
    }
    md += `\n`;

    if (analysis.lowYieldSuggestions.length > 0) {
      md += `## 3. Route Yield & Optimization Recommendations\n\n`;
      md += `The following traversed paths yielded minimal or zero document assets:\n\n`;
      for (const item of analysis.lowYieldSuggestions) {
        md += `* **\`${item.section}\`** (${item.pagesCrawled} pages explored) — *${item.reason}*\n`;
      }
      md += `\n`;
    }

    if (analysis.taxonomyDistribution.length > 0) {
      md += `## 4. Taxonomy Category Coverage\n\n`;
      md += `| Category Code | Label | Documents Found |\n| :--- | :--- | :--- |\n`;
      for (const tax of analysis.taxonomyDistribution) {
        md += `| \`${tax.code}\` | ${tax.label} | **${tax.count}** |\n`;
      }
      md += `\n`;
    }

    if (analysis.taxonomyGaps.length > 0) {
      md += `### Identified Taxonomy Gaps\n\n`;
      for (const gap of analysis.taxonomyGaps) {
        md += `* ⚠️ **${gap.label} (\`${gap.code}\`)**: ${gap.message}\n`;
      }
      md += `\n`;
    }

    md += `---\n*Report generated by the AegisArchive Forensic Diagnostic Engine.*`;
    return md;
  }

  return {
    analyze,
    generateMarkdownReport
  };
}));
