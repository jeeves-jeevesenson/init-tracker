# Monster Data Source Research

## 1. Executive Summary
This document evaluates external monster data sources to determine the best path for migrating `init-tracker` from display-only legacy YAMLs to structured, executable monster capabilities.

## 2. Sources Evaluated

### 2.1 Legacy Monsters/*.yaml
- **Status:** Current local data.
- **Payload:** Flat YAML with AideDD-style markup (`{@hit}`, etc.).
- **Strengths:** Already in repo; 514 monsters covered.
- **Weaknesses:** Mostly display text; reactions missing; multiattack/recharge not structured; spellcasting mostly empty.

### 2.2 Open5e (V2 API)
- **Status:** Public API (open5e.com).
- **Payload:** Highly structured JSON with fields for `actions`, `reactions`, `legendary_actions`, `special_abilities`, `skills`, `saves`, etc.
- **Strengths:** Very detailed; includes non-SRD open content (Tome of Beasts, etc.); robust filtering.
- **Weaknesses:** Some content may vary in formatting; V2 API is relatively new.
- **Recommendation:** **Primary Source** for bulk import and normalization.

### 2.3 dnd5eapi (5e-bits)
- **Status:** Public API (dnd5eapi.co).
- **Payload:** Structured JSON focused on SRD 5.1 content.
- **Strengths:** Clean, standard SRD data; widely used by developers.
- **Weaknesses:** Smaller scope (SRD only); less diversity in monsters compared to Open5e.
- **Recommendation:** **Secondary Source** for validation and clean SRD baselines.

### 2.4 SRD 5.2.1 / 2024 Rules
- **Status:** Official WotC baseline under CC-BY-4.0.
- **Licensing:** Irrevocable, allows commercial use with attribution.
- **Availability:** May 1, 2025 release.
- **Recommendation:** Use as the **Legal Gold Standard**. Ensure all imported content includes appropriate attribution.

## 3. Findings

### 3.1 Payload Comparison
| Feature | Legacy | Open5e | dnd5eapi |
|---|---|---|---|
| Structured Actions | No | Yes | Yes |
| Multiattack Support | No | Partially (text) | Partially (options) |
| Reactions | No | Yes | No |
| Legendary Actions | Yes (list) | Yes (structured) | Yes (list) |
| Spellcasting | Very Limited | Link to spells | References |

### 3.2 Licensing Notes
- Open5e content is generally OGL or Creative Commons.
- `init-tracker` must avoid storing "Product Identity" (e.g., Beholders, Mind Flayers) from proprietary sources.
- Open5e's "Srd" document key is the safest starting point.

## 4. Decision: Internal Normalized Schema
`init-tracker` should own its internal normalized capability schema to avoid vendor lock-in. This allows the project to:
1. Merge data from multiple sources.
2. Add custom execution logic for the specific backend.
3. Decouple the UI from external API changes.

## 5. Short-term Strategy
1. Implement a prototype importer for Open5e data.
2. Focus on a small set of "Hero Monsters" (Skeleton, Goblin, Dragon, Lich).
3. Generate sample normalized YAMLs for review.

## 6. Long-term Strategy
- Shift toward a "Capability Overlay" model where structured data enhances legacy YAMLs.
- Build a DM-facing authoring tool to refine and validate generated capabilities.
