# 🎮 Quiz Adventure (erillinen HTML5-demo)

Tämä on **itsenäinen peli-demo**, jota voi ajaa suoraan selaimessa ilman palvelinta.  
Pelin avulla voidaan generoida monivalintakysymyksiä suomeksi mihin tahansa aiheeseen (matematiikka, historia, kirjallisuus, luonnontiede, …).

---

---

## ▶️ Käynnistys

- Avaa `index.html` selaimessa:
  - **Live Server (suositeltu):**  
    Asenna VS Code -lisäosa *Live Server*. Avaa `index.html` → hiiren oikea → *Open with Live Server*.  
    → Näet pelin selaimessa osoitteessa `http://127.0.0.1:5500/`.
  - **Tuplaklikkaus:**  
    Avaa `index.html` tuplaklikkaamalla. Tämäkin toimii, mutta kaikki selaimet eivät salli `fetch()`-kutsuja tiedostosta.

---

## 🔑 OpenAI API-avain

- Pelin vasemmalla puolella on kenttä **“OpenAI API-avain”**.  
- Liitä sinne oma avaimesi (esim. `sk-...`).  
- Avain **ei tallennu** mihinkään, se pysyy vain selaimen muistissa.  
- “Poista avain” -nappi tyhjentää sen heti.

⚠️ **Huomio:** Tässä demossa avain välitetään suoraan selaimesta OpenAI:lle → käytä vain kehityksessä.  
Kun peli liitetään Django/Flask -projektiin, siirretään kutsu palvelimelle ja avain haetaan **ympäristömuuttujasta**.

---

## 🧪 Testidata ilman API:a

Jos haluat kokeilla peliä ilman API-avainta:
- Klikkaa nappia **“Luo testidata ilman API:a”**.  
- Tämä luo valmiin esimerkkipelin (mm. “Seitsemän veljestä”, “veden kaava”, “7×8”).  

---

## 🎨 Ominaisuudet

- Suomeksi toimiva käyttöliittymä.
- Kysymykset generoidaan OpenAI:n avulla.
- Monivalinta, pistelaskuri, etenemispalkki.
- Responsiivinen (Bootstrap 5), toimii myös mobiilissa.
- Kaikki sisäänrakennettuna **yhteen tiedostoon (`index.html`)**.

---
