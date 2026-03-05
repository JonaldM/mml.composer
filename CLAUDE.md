# MML Consumer Products — Odoo Module Architecture

> **For Claude:** Read this file first before touching any module. It defines intent, boundaries, and wiring.

## Company Context

MML Consumer Products Ltd is a New Zealand-based distribution company. We distribute ~400 SKUs across 5 brands (Volere, Annabel Langbein, Enkel, Enduro, Rufus & Coco) to major NZ/AU retail chains. We run a self-hosted Odoo 19 instance.

**Currently deployed as internal operational infrastructure for MML Consumer Products. Architecture is being built with a SaaS pivot in mind — each module is a sellable, independently installable Odoo app.** Every module must be production-safe, auditable, and designed for a small ops team (not engineers) to use day-to-day.

---

## Module Map

```
mml_odoo/
├── CLAUDE.md                  ← You are here. Read this first.
├── mml_3pl/                   ← Mainfreight 3PL warehouse integration
├── mml_freight_forwarder/     ← DSV + multi-carrier freight forwarding with tender
├── mml_edi/                   ← EDI integrations for retail partners
└── .claude/                   ← Session context, scratchpad
```

---

## Module 1: `mml_3pl` — Third-Party Logistics (Mainfreight)

**Intent:** Automate warehouse operations by integrating Odoo with Mainfreight's 3PL systems. Odoo is the source of truth for inventory and orders; Mainfreight is the physical execution layer.

**Core flows:**
- Outbound: SO confirmed → despatch request to Mainfreight → pick/pack/ship → tracking returned → DO updated
- Inbound: PO received at Mainfreight → receipt confirmation → stock levels updated in Odoo
- Inventory sync: Periodic stock reconciliation between Mainfreight WMS and Odoo quants

**Key design decisions:**
- Async messaging (not real-time blocking API calls)
- Mainfreight API responses create `mail.message` audit trail on SO/PO/DO
- Stock discrepancies flagged but never auto-corrected without human review
- Retry with exponential backoff; dead-letter queue for failed calls

**Depends on:** `stock`, `sale`, `purchase`
**Aware of:** `mml_freight_forwarder` (freight costs → landed cost), `mml_edi` (EDI orders trigger 3PL despatch)

---

## Module 2: `mml_freight_forwarder` — Freight Forwarding & Tender

**Intent:** Manage international freight forwarding (inbound supply from overseas manufacturers to NZ) with multi-carrier quoting and tender functionality. DSV is primary forwarder; architecture supports adding others.

**Core flows:**
- Shipment creation: PO confirmed → freight shipment record → linked to PO lines
- Tender/quote: Request quotes from multiple forwarders (DSV API + manual) → compare → award
- Tracking: Milestone updates from forwarder APIs → status visible on PO
- Landed cost: Freight + duties + insurance → product landed cost for margin accuracy

**Key design decisions:**
- Carrier abstraction layer — each carrier is a provider class with common interface
- DSV API is the reference implementation
- Tender workflow: Draft → Quotes Requested → Quotes Received → Awarded → In Transit → Delivered
- All freight costs linked to `stock.landed.cost` records
- Currency handling: quotes in USD/EUR, convert to NZD at booking rate

**Depends on:** `stock`, `purchase`, `account`
**Aware of:** `mml_3pl` (inbound shipments arrive at Mainfreight — handoff point), `mml_edi` (EDI POs may trigger upstream purchasing/freight)

---

## Module 3: `mml_edi` — Electronic Data Interchange (Retail Partners)

**Intent:** Automate order, invoice, and despatch advice exchange with retail partners. Reduce manual entry, speed order-to-despatch, eliminate keying errors.

**Core flows:**
- Inbound: Partner PO (850/ORDERS) → parsed → Odoo SO created
- Outbound: Despatch confirmed → ASN (856/DESADV) sent to partner
- Outbound: Invoice validated → EDI invoice (810/INVOIC) sent to partner
- Optional: Inventory report (846/INVRPT) for partners requiring stock availability

**Key design decisions:**
- Each partner = a profile with its own mapping, transport, and document config
- EDI documents stored as `ir.attachment` with full audit trail
- Pluggable document engine (not hardcoded per partner)
- Exception queue with manual review UI for failed documents
- All EDI actions create `mail.message` on related SO/PO/invoice

**Depends on:** `sale`, `account`, `stock`
**Aware of:** `mml_3pl` (ASN depends on Mainfreight despatch confirmation), `mml_freight_forwarder` (freight status affects promise dates)

---

## Cross-Module Awareness Matrix

Modules don't directly import each other's Python code. Awareness is via:

1. **Shared Odoo models** — all modules read/write SO, PO, stock.picking, account.move
2. **Chatter signals** — modules post `mail.message` updates; others can subscribe
3. **Computed fields** — e.g., SO shows 3PL status AND EDI status without coupling
4. **Cron-based orchestration** — scheduled actions check cross-module state

| Trigger Event | Source | Consumer | Action |
|---|---|---|---|
| SO confirmed (EDI partner) | `mml_edi` | `mml_3pl` | Queue despatch request to Mainfreight |
| Mainfreight despatch confirmed | `mml_3pl` | `mml_edi` | Generate & send ASN to retail partner |
| Mainfreight despatch confirmed | `mml_3pl` | `sale` | Update DO, notify customer |
| PO confirmed (international) | `purchase` | `mml_freight_forwarder` | Create shipment, request quotes |
| Freight delivered to Mainfreight | `mml_freight_forwarder` | `mml_3pl` | Trigger inbound receipt |
| Invoice validated (EDI partner) | `account` | `mml_edi` | Generate & send EDI invoice |
| EDI PO received | `mml_edi` | `sale` | Create/update SO |
| Freight landed cost finalised | `mml_freight_forwarder` | `account` | Update product cost, recalc margins |

---

## EDI Partner Profiles

### Briscoes Group (Briscoes, Rebel Sport, Living & Giving)

| Field | Detail |
|---|---|
| Transport | SFTP (Briscoes-hosted or VAN) |
| Inbound docs | Purchase Order (ORDERS / 850) |
| Outbound docs | ASN (DESADV / 856), Invoice (INVOIC / 810) |
| Format | EDIFACT or CSV — confirm with Briscoes IT |
| Identifiers | GLN for ship-to locations |
| Requirements | EAN-13 barcode mandatory on ASN lines; SSCC carton labelling likely required; compliance chargebacks for ASN failures |
| Status | Scope defined, awaiting partner technical spec |

### Harvey Norman NZ

| Field | Detail |
|---|---|
| Transport | SFTP or VAN (MessageXchange / SPS Commerce) |
| Inbound docs | Purchase Order (ORDERS / 850) |
| Outbound docs | ASN (DESADV / 856), Invoice (INVOIC / 810) |
| Format | EDIFACT preferred (AU/NZ standard) |
| Identifiers | GLN for store/DC locations |
| Requirements | NZ-specific spec (may differ from AU); DC vs store-direct affects ASN structure; cross-dock routing codes |
| Status | Scope defined, awaiting partner technical spec |

### Animates (Pet retail)

| Field | Detail |
|---|---|
| Transport | TBC — may be CSV/email initially, SFTP target |
| Inbound docs | Purchase Order |
| Outbound docs | Order Confirmation, ASN, Invoice |
| Format | CSV initially, migrate to EDIFACT |
| Requirements | Pet product compliance fields (registration numbers, batch/lot for consumables); may require inventory availability reporting |
| Status | Scope defined, format TBC |

### PetStock (AU/NZ)

| Field | Detail |
|---|---|
| Transport | TBC — likely SPS Commerce or direct SFTP |
| Inbound docs | Purchase Order |
| Outbound docs | ASN, Invoice |
| Format | TBC |
| Requirements | AU-based — may need AU-format EDIFACT; cross-border shipping considerations; Rufus & Coco brand alignment |
| Status | Early scope, awaiting engagement |

### Adding New Partners

Architecture must support adding new partners via configuration, not code. Each partner profile contains: transport config, document mappings, GLN/identifiers, validation rules, chargeback/compliance rules.

---

## Technical Standards (All Modules)

### Odoo Conventions
- Module prefix: `mml_`
- Model naming: `mml.3pl.despatch`, `mml.freight.shipment`, `mml.edi.document`
- Security: `ir.model.access.csv` + record rules per module
- Views: form, tree, kanban for pipeline/status views
- Menus: each module is a **standalone Odoo app** — own root menuitem (no `parent=`), own `web_icon`, `application = True` in manifest. Bridge/platform modules (`mml_base`, `mml_roq_freight`, `mml_freight_3pl`) are exceptions: `application = False`, no menu.

### API Integration Pattern
- All external API calls via `mml.api.client` base class
- Retry: exponential backoff, max 3, then dead-letter
- All requests/responses logged as `ir.attachment`
- Credentials in `ir.config_parameter`, never hardcoded
- Prefer async (OCA `queue_job` or cron polling)

### Error Handling
- Failed ops → exception queue (dedicated tree view per module)
- Email alerts on critical failures
- Never silently swallow errors
- Never auto-modify financial/stock data on discrepancies without human confirm

### Testing
- Unit tests for all API parsing/generation
- Integration stubs with mock API responses
- Run with `--test-enable`

---

## For Claude: Working on This Project

1. **Read this file first.** Understand where the module sits.
2. **Respect boundaries.** No hard imports between mml_3pl, mml_freight_forwarder, mml_edi. Use standard Odoo model inheritance and computed fields.
3. **Production mindset.** Real business. Audit trails, error handling, data integrity are non-negotiable.
4. **Odoo 19.** OWL for frontend, standard ORM for backend.
5. **Don't invent specs.** If a partner's EDI format isn't confirmed, scaffold the interface but mark it TBC.
6. **Check .claude/ for session notes** from previous work sessions before starting.
