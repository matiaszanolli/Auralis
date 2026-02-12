# Auralis Licensing Strategy

## Overview

Auralis uses a **dual licensing model** that keeps the project fully open source for the community while requiring a commercial license for proprietary and for-profit embedded use.

---

## License Structure

### Open Source License: AGPL-3.0

**Applies to:** Everyone, by default.

The entire Auralis codebase — the player, the mastering algorithm, the 25D/26D fingerprinting system, the Rust DSP bindings — is released under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This means anyone can:

- Use Auralis for personal or organizational use
- Study, modify, and redistribute the source code
- Build derivative works and products
- Use it commercially in open-source products

With one requirement: **any derivative work, including server-side deployments, must also be released under AGPL-3.0 with full source code.**

#### Why AGPL-3.0 instead of GPL-3.0

Auralis is currently licensed under GPL-3.0. The recommendation is to migrate to AGPL-3.0 because:

- **GPL-3.0 has a server-side loophole.** A streaming service, cloud DAW, or SaaS product could run Auralis on their servers, deliver processed audio to users, and never distribute the software — meaning GPL never triggers. They get the algorithm for free with no obligation to open-source anything.
- **AGPL-3.0 closes this gap.** If a service interacts with users over a network using Auralis (or a derivative), they must provide the complete source code of their version, including modifications.
- **For individual users and open-source contributors, nothing changes.** AGPL-3.0 grants the same freedoms as GPL-3.0.

#### Migration Path

Since Matías is the sole copyright holder, relicensing from GPL-3.0 to AGPL-3.0 requires:

1. Update `LICENSE` in the repository
2. Update license headers in source files
3. Update `pyproject.toml`, `package.json`, and README badges
4. Tag the relicense in the CHANGELOG
5. Existing GPL-3.0 releases remain under GPL-3.0 (only new versions are AGPL-3.0)

Note: If any third-party contributions have been accepted under GPL-3.0, those contributors would need to consent to relicensing, or their code would need to be rewritten. Review the 6 contributors listed on GitHub before proceeding.

---

### Commercial License: Auralis Commercial License (ACL)

**Applies to:** Any entity that wants to use Auralis or its algorithms in a proprietary (closed-source) context for profit.

#### When a Commercial License Is Required

A commercial license is required when **all three** of the following are true:

1. **Proprietary use** — The product or service using Auralis does not release its complete source code under AGPL-3.0.
2. **For profit** — The entity generates revenue from the product or service (directly or indirectly).
3. **Distribution or network use** — The product is distributed to users or interacts with users over a network.

#### Specific Scenarios

| Scenario | License Required |
|----------|-----------------|
| Individual listening to music with Auralis | AGPL-3.0 (free) |
| Open-source project integrating Auralis | AGPL-3.0 (free) |
| University research using Auralis | AGPL-3.0 (free) |
| Non-profit using Auralis internally | AGPL-3.0 (free) |
| Company using Auralis internally (not distributed) | AGPL-3.0 (free) |
| Streaming service using Auralis server-side | **Commercial license** |
| TV manufacturer embedding the algorithm in firmware | **Commercial license** |
| DAW or audio software shipping Auralis as a plugin | **Commercial license** |
| Headphone/speaker company using the algorithm in DSP chips | **Commercial license** |
| Music production SaaS using Auralis in its pipeline | **Commercial license** |
| Mobile app using Auralis with closed-source code | **Commercial license** |

---

## Commercial License Tiers

The commercial license uses a **symbolic base fee** with revenue-based scaling for large deployments. The intent is not to create a profit center from licensing, but to establish the principle that corporate profit from Auralis requires acknowledgment and fair contribution.

### Tier 1: Indie & Startup

**For:** Companies with annual revenue under $1M USD.

- **Fee:** $100 USD / year
- **Includes:** Full commercial use rights, proprietary distribution, embedded use
- **Support:** Community only (GitHub Issues)

### Tier 2: Business

**For:** Companies with annual revenue between $1M and $50M USD.

- **Fee:** $1,000 USD / year
- **Includes:** Everything in Tier 1, plus priority issue handling
- **Support:** Email support with 5 business day response time

### Tier 3: Enterprise & Embedded

**For:** Companies with annual revenue over $50M USD, or any company embedding the algorithm in hardware shipped to consumers.

- **Fee:** $5,000 USD / year (base), or negotiated per-unit royalty for high-volume hardware
- **Includes:** Everything in Tier 2, plus custom licensing terms
- **Support:** Direct communication channel, 2 business day response time

### Tier 4: Negotiated

**For:** Deployments exceeding 10 million units, or use cases not covered above.

- **Fee:** Negotiated
- **Terms:** Custom agreement

### Notes on Pricing

- All tiers are **annual**, renewable.
- Fees are intentionally modest. The goal is establishing a legal and ethical framework, not maximizing revenue.
- "Revenue" refers to the entity's total annual revenue, not revenue attributable to Auralis specifically.
- A 30-day evaluation period is granted at no cost for any tier.

---

## Governance & Contributor Licensing

### Contributor License Agreement (CLA)

To maintain the ability to dual-license, all contributors must sign a **Contributor License Agreement** granting Matías Zanolli (or a designated legal entity) the right to sublicense their contributions under the commercial license.

Without a CLA, contributed code can only be distributed under AGPL-3.0, which would prevent dual licensing for those portions.

Recommended CLA terms:

- Contributors retain copyright of their contributions.
- Contributors grant the project maintainer a perpetual, worldwide, non-exclusive license to sublicense the contribution under any terms (including the commercial license).
- Contributors confirm the contribution is their original work (or properly attributed).

Tools like [CLA Assistant](https://cla-assistant.io/) can automate this via GitHub pull requests.

### Future Entity

As commercial licensing activity grows, consider establishing a legal entity (e.g., "Auralis Audio" or similar) to:

- Hold the copyright and commercial license
- Issue invoices and receive payments
- Provide legal separation between personal and project finances
- Enable potential fiscal sponsorship or foundation structure later

---

## Enforcement & Compliance

### Detection

- Monitor package registries (npm, PyPI, crates.io) for unauthorized derivatives.
- Set up GitHub alerts for forks and downstream projects.
- Periodically review embedded audio products and streaming services for fingerprints of Auralis processing (the 25D signature itself could serve as a forensic marker).

### Response Escalation

1. **Friendly notice** — Contact the entity, inform them of the licensing terms, offer the commercial license.
2. **Formal request** — Written notice with a 30-day compliance window.
3. **AGPL enforcement** — If they refuse to either open-source their derivative or purchase a commercial license, pursue AGPL enforcement (organizations like the [Software Freedom Conservancy](https://sfconservancy.org/) can assist).

### Philosophy

The intent is never adversarial. The licensing exists to ensure that corporations who profit from the work contribute fairly. The escalation path starts with a conversation, not a legal threat.

---

## Implementation Checklist

### Immediate

- [ ] Audit the 6 existing contributors for relicensing consent
- [ ] Draft and adopt a CLA for future contributions
- [ ] Relicense from GPL-3.0 to AGPL-3.0
- [ ] Add `COMMERCIAL_LICENSE.md` to the repository with terms summary
- [ ] Update README with dual licensing notice
- [ ] Add license header to all source files

### Short-term

- [ ] Set up CLA Assistant on GitHub
- [ ] Create a licensing page on the project website (or a dedicated section in docs)
- [ ] Prepare a commercial license agreement template (consult an attorney for final review)
- [ ] Set up a payment mechanism (Stripe, GitHub Sponsors, or invoicing)

### Medium-term

- [ ] Consider establishing a legal entity
- [ ] Implement compliance monitoring
- [ ] Develop a "Powered by Auralis" badge program for licensed commercial users

---

## Repository License Notice

The following notice should appear in the repository README and in source file headers:

### README Addition

```
## License

Auralis is dual-licensed:

- **Open Source:** AGPL-3.0 — free for personal use, research, education,
  and open-source projects. See [LICENSE](LICENSE).
- **Commercial:** For proprietary, embedded, or closed-source commercial use,
  a commercial license is required. See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)
  or contact contacto@matiaszanolli.com.
```

### Source File Header

```python
# Auralis - Open Source Media Player with Audio Mastering
# Copyright (C) 2024-2026 Matías Zanolli
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# For commercial/proprietary use, contact: contacto@matiaszanolli.com
```

---

## Comparable Projects Using This Model

| Project | Open License | Commercial Model |
|---------|-------------|-----------------|
| Qt | LGPL / GPL | Per-developer commercial license |
| MongoDB | SSPL | MongoDB Atlas (hosted service) |
| Grafana | AGPL-3.0 | Grafana Cloud + Enterprise license |
| Minio | AGPL-3.0 | Commercial license for OEM/embedded |
| Nextcloud | AGPL-3.0 | Enterprise subscription |
| iText (PDF) | AGPL-3.0 | Commercial license for proprietary use |

Auralis fits cleanly into this pattern: AGPL-3.0 for the community, commercial license for proprietary profit.

---

*Document prepared February 2026. Consult a qualified intellectual property attorney before finalizing commercial license terms.*