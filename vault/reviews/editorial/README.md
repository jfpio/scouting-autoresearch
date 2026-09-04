# Oceny redakcyjne aktywności

Ocena wartości i bezpieczeństwa jest niezależna od oceny praw i wiarygodności źródła.
Rekord wskazuje konkretną aktywność oraz jej `sourceHash`; zmiana tekstu unieważnia ocenę.

`inbox/` zawiera puste formularze wymagające decyzji człowieka. Agent może je przygotować,
ale nie może uzupełniać ocen ani oznaczać ich jako zatwierdzone. Po ręcznej ocenie rekord
może trafić do `accepted/` z datą, osobą oceniającą i uzasadnieniem. Rekomendacja publikacyjna
nie zmienia sama eksportów, treści źródłowej, tłumaczenia ani statusu prawnego.

Nowy formularz można przygotować poleceniem:

```bash
python scripts/prepare_editorial_review.py --activity-id bsh-001
```
