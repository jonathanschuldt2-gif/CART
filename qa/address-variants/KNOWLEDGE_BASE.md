# Address Variant Knowledge Base

Reference data for generating shipping-validation address variants.

Sources:
- USPS Publication 28, Appendix C1 – Street Suffix Abbreviations: https://pe.usps.com/text/pub28/28apc_002.htm
- USPS Publication 28, Appendix C2 – Secondary Unit Designators: https://pe.usps.com/text/pub28/28apc_003.htm

## C1 – Street Suffix Abbreviations (common subset)

Format: primary name | common variants seen in the wild | USPS standard abbreviation

| Primary | Commonly used variants | USPS standard |
|---|---|---|
| AVENUE | AV, AVE, AVEN, AVENU, AVENUE, AVN, AVNUE | AVE |
| BOULEVARD | BLVD, BOUL, BOULEVARD, BOULV | BLVD |
| CIRCLE | CIR, CIRC, CIRCL, CIRCLE, CRCL, CRCLE | CIR |
| COURT | COURT, CT | CT |
| COVE | COVE, CV | CV |
| DRIVE | DR, DRIV, DRIVE, DRV | DR |
| EXPRESSWAY | EXP, EXPR, EXPRESS, EXPRESSWAY, EXPW, EXPY | EXPY |
| HIGHWAY | HIGHWAY, HIGHWY, HIWAY, HIWY, HWAY, HWY | HWY |
| LANE | LANE, LN | LN |
| PARKWAY | PARKWAY, PARKWY, PKWAY, PKWY, PKY | PKWY |
| PLACE | PL | PL |
| PLAZA | PLAZA, PLZ, PLZA | PLZ |
| ROAD | RD, ROAD | RD |
| SQUARE | SQ, SQR, SQRE, SQU, SQUARE | SQ |
| STREET | STREET, STRT, ST, STR | ST |
| TERRACE | TER, TERR, TERRACE | TER |
| TRAIL | TRAIL, TRAILS, TRL, TRLS | TRL |
| WAY | WAY, WY | WAY |

See the source page for the full list of ~200 suffixes.

## C2 – Secondary Unit Designators

`*` = does not require a secondary range number.

| Description | Approved abbreviation |
|---|---|
| APARTMENT | APT |
| BASEMENT* | BSMT |
| BUILDING | BLDG |
| DEPARTMENT | DEPT |
| FLOOR | FL |
| FRONT* | FRNT |
| HANGAR | HNGR |
| KEY | KEY |
| LOBBY* | LBBY |
| LOT | LOT |
| LOWER* | LOWR |
| OFFICE* | OFC |
| PENTHOUSE* | PH |
| PIER | PIER |
| REAR* | REAR |
| ROOM | RM |
| SIDE* | SIDE |
| SLIP | SLIP |
| SPACE | SPC |
| STOP | STOP |
| SUITE | STE |
| TRAILER | TRLR |
| UNIT | UNIT |
| UPPER* | UPPR |

Notes:
- `#` may be used in place of a designator when the designator is unknown (e.g. `# 6B`); USPS requires a space between `#` and the range.
- `GDN` (garden) is **not** a USPS-approved designator — it is common in Chicago-area addresses and is a good normalization test case (`APT GDN`, `UNIT GDN`, `# GDN`).

## Variation techniques

- **Suffix variation:** swap in any C1 variant (`Avenue ↔ Aven ↔ Ave ↔ ave ↔ Avn ↔ Avnue`).
- **Formatting noise:** extra hyphens (`909-Bronco Wy`), extra spaces (`90 9 Bron co Wy`), missing spaces (`909 BroncoWy`), case changes, trailing periods.
- **Minor typos:** transposed (`Bertaeu`), doubled (`Beerteau`), dropped (`Berteu`), number/letter substitution (`185B` B↔8, `18S8` S↔8, `I858` I↔1).
- **Line 2 appended junk:** 1–2 alphanumeric characters appended to a C2 designator (`APT GDN-12`, `OFC 1C`, `FL 1 APT C`).
