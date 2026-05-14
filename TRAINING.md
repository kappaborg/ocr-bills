# Training your own OCR / receipt model (annotations → F1)

This project currently uses **Tesseract + heuristics** (and optional cloud OCR later). To reach **high F1** on *your* receipts (Latin + Cyrillic, BAM, etc.), treat it as a **dataset + evaluation** problem—not only “more languages in Tesseract.”

## 1. What to label (targets)

Pick one primary task first (narrow scope = higher quality):

| Task | Labels | Typical F1 meaning |
|------|--------|---------------------|
| **Line items** | `item_name`, `item_price`, optional `qty`, `unit_price` | Micro-F1 over extracted fields vs gold |
| **Key fields** | `store_name`, `receipt_date`, `total`, `currency` | Exact match or normalized match |
| **Language** | ISO 639-1 code | Accuracy / macro-F1 per class |

For receipts, **sequence labeling** (each token B-I-O for `ITEM`, `PRICE`, `DATE`) or **JSON extraction** (layout LM–style) are common.

## 2. Dataset format (minimal)

Store one JSON line per receipt (or one folder per image):

```json
{
  "image": "receipts/sample_001.jpg",
  "ocr_text": "<optional raw OCR for weak supervision>",
  "language": "bs",
  "currency": "BAM",
  "store": "GREEN FIELD",
  "date": "2016-05-26",
  "total": 51.9,
  "items": [
    { "name": "Coffee", "price": 3.0 },
    { "name": "Lunch", "price": 45.9 }
  ]
}
```

Keep **train / val / test splits** (e.g. 70/15/15) by **receipt**, not by line, to avoid leakage.

## 3. Metrics (F1)

- **Field-level**: For each field, precision/recall/F1 (e.g. total within 0.01 of truth).
- **Item-level**: Match predicted lines to gold (Hungarian matching on price + fuzzy name), then precision/recall/F1.
- **Language**: Macro-F1 per language if imbalanced.

## 4. Practical training path

1. **Export gold labels** from your app once “edit before confirm” exists (store corrections vs raw OCR).
2. **Baseline**: current pipeline on the test set → measure F1.
3. **Improve OCR**: `eng+rus+srp` (or cloud OCR) + image preprocessing grid-search on val only.
4. **Model**: fine-tune a **document understanding** model (e.g. Donut / LayoutLMv3 class of models) on your JSON labels, or train a **CRF / transformer** on OCR tokens.

## 5. Language detection for training

- Log **`detected_language`** (e.g. `langdetect`) vs **human label** in `language` to measure detection accuracy separately from extraction F1.

---

Use this file as a checklist when you add an **export endpoint** or **CSV/JSON dump** of confirmed receipts for offline training.
