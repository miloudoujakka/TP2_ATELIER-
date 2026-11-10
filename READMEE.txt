## La Structure :

```
tp2_atelier/
|-- atelier.py        # lecture, validation, analyse, rapport
|-- exceptions.py     # AtelierError, FichierInvalide, ReleveInvalide
|-- main.py           # programme principal
|-- donnees/          # machines.json, releves.csv, evenements.log
|-- tests/            # tests des étapes 1 à 8 + test_mes_tests.py
|-- pytest.ini
`-- requirements.txt


```

Résultats attendu :

14 relevés valides, 5 lignes rejetées
8 alertes ; machines à surveiller : M-01, M-02, M-04, M-03
Sans relevé : M-05
Fichiers écrits dans sorties/ : rejets.csv, rapport.json
```

## Comment pouir tester :

```
pytest
```
