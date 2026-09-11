# Shipping Address Variants — QA Fixture

Synthetic address variants for shipping-normalization QA testing, generated
from a single source address.

**Source address**
- Line 1: `1858 W Berteau Ave`
- Line 2: `Apt GDN`
- City: `Chicago`
- Zip: `60613`

**File:** `berteau_ave_variants.csv`

25 variants, each with a unique Line 1 (2-3 combined techniques: suffix
abbreviation/casing, directional expansion, formatting noise like extra/
missing spaces or hyphens, and typos such as transposed/doubled letters or
digit-letter substitution) and Line 2 always `APT GDN` plus 1-2 characters
of appended junk. 18/25 (72%) are minor variations expected to be
deliverable as-is; 7/25 (28%) are more challenging (wrong suffix family,
wrong directional, transposed digits) meant to stress-test the normalizer.
