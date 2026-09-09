# Specification

AC1: JSON reports distinguish attempts from saved responses; failures never imply optimal health.
AC2: Record transport/body/archive failure stages and native underlying exception types without credential values. Save JSON beside USB capture logs and provide download fallback.
AC3: Sanitised, deduplicated intake findings support agent triage, reproduction, remediation and regression verification. Never automatically upload private reports.
AC4: Synthetic regression tests cover the reported zero-capture misleading-summary failure.
