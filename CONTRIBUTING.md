# Współpraca

Zmiany przyjmujemy przez pull requesty. Przed wysłaniem uruchom:

```bash
.venv/bin/python scripts/build_content.py
.venv/bin/python scripts/validate.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
npm run build
.venv/bin/python scripts/check_links.py
```

Korekta tekstu źródłowego wymaga wskazania strony skanu. Zmiana oryginału unieważnia
tłumaczenie, dopóki plik tłumaczenia nie otrzyma zgodnego `sourceHash`. Nowe źródło wymaga
rekordu bibliograficznego, dowodu statusu prawnego i zatwierdzenia człowieka.

Zgłoszenia dotyczące bezpieczeństwa aktywności powinny rozróżniać historyczną transkrypcję od
współczesnej rekomendacji. Nie dopisujemy parametrów, których źródło nie podaje.
